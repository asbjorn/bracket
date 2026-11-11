from decimal import Decimal

import pytest
from heliclockter import datetime_utc

from bracket.logic.ranking.statistics import TeamStatistics
from bracket.logic.ranking.tiebreakers import (
    TiebreakerData,
    head_to_head_points,
    order_by_ranking,
)
from bracket.models.db.match import MatchWithDetailsDefinitive
from bracket.models.db.ranking import DEFAULT_TIEBREAKERS, Ranking, RankingBody, Tiebreaker
from bracket.models.db.stage_item_inputs import StageItemInputEmpty
from bracket.utils.id_types import MatchId, RankingId, RoundId, StageItemInputId, TournamentId

NOW = datetime_utc.now()
A, B, C, D = (StageItemInputId(i) for i in (1, 2, 3, 4))


def ranking(tiebreakers: list[Tiebreaker]) -> Ranking:
    return Ranking(
        id=RankingId(1),
        tournament_id=TournamentId(1),
        created=NOW,
        position=0,
        win_points=Decimal("3"),
        draw_points=Decimal("1"),
        loss_points=Decimal("0"),
        add_score_points=False,
        tiebreakers=tiebreakers,
    )


def played(
    input1: StageItemInputId, input2: StageItemInputId, score1: int, score2: int
) -> MatchWithDetailsDefinitive:
    def input_(input_id: StageItemInputId) -> StageItemInputEmpty:
        return StageItemInputEmpty(id=input_id, slot=input_id, tournament_id=TournamentId(1))

    return MatchWithDetailsDefinitive(
        id=MatchId(input1 * 10 + input2),
        created=NOW,
        duration_minutes=10,
        margin_minutes=5,
        round_id=RoundId(1),
        stage_item_input1_id=input1,
        stage_item_input2_id=input2,
        stage_item_input1=input_(input1),
        stage_item_input2=input_(input2),
        stage_item_input1_score=score1,
        stage_item_input2_score=score2,
        stage_item_input1_conflict=False,
        stage_item_input2_conflict=False,
        played=True,
    )


def stats(points: int, goals_for: int, goals_against: int) -> TeamStatistics:
    return TeamStatistics(points=Decimal(points), goals_for=goals_for, goals_against=goals_against)


def test_points_decide_first() -> None:
    table = {A: stats(3, 0, 5), B: stats(6, 1, 0)}
    assert order_by_ranking(
        [A, B], table, [], ranking(DEFAULT_TIEBREAKERS), use_tiebreakers=True
    ) == [
        B,
        A,
    ]


def test_goal_difference_then_goals_scored() -> None:
    table = {
        A: stats(4, 3, 3),  # difference 0, scored 3
        B: stats(4, 5, 2),  # difference 3
        C: stats(4, 5, 5),  # difference 0, scored 5
    }
    order = order_by_ranking(
        [A, B, C], table, [], ranking(DEFAULT_TIEBREAKERS), use_tiebreakers=True
    )
    assert order == [B, C, A]


def test_head_to_head_only_counts_matches_between_tied_teams() -> None:
    """
    A and B are equal on points and goals. B beat A, so B is ahead, even though A won its match
    against C (which is not tied with them).
    """
    matches = [played(A, B, 0, 1), played(A, C, 2, 0), played(B, C, 0, 1)]
    # A and B: equal points, goal difference and goals scored
    table = {A: stats(3, 2, 1), B: stats(3, 2, 1), C: stats(3, 1, 2)}
    order = order_by_ranking(
        [A, B, C], table, matches, ranking(DEFAULT_TIEBREAKERS), use_tiebreakers=True
    )
    assert order == [B, A, C]
    assert head_to_head_points([A, B], matches, ranking(DEFAULT_TIEBREAKERS)) == {
        A: Decimal("0"),
        B: Decimal("3"),
    }


def test_order_of_tiebreakers_matters() -> None:
    """
    B has the better goal difference, but A beat B: the configured order decides.
    """
    matches = [played(A, B, 1, 0)]
    table = {A: stats(3, 1, 4), B: stats(3, 6, 2)}

    goal_difference_first = ranking([Tiebreaker.GOAL_DIFFERENCE, Tiebreaker.HEAD_TO_HEAD])
    head_to_head_first = ranking([Tiebreaker.HEAD_TO_HEAD, Tiebreaker.GOAL_DIFFERENCE])

    assert order_by_ranking(
        [A, B], table, matches, goal_difference_first, use_tiebreakers=True
    ) == [
        B,
        A,
    ]
    assert order_by_ranking([A, B], table, matches, head_to_head_first, use_tiebreakers=True) == [
        A,
        B,
    ]


def test_circular_head_to_head_falls_through_and_keeps_slot_order() -> None:
    """
    A beat B, B beat C, C beat A, all 1-0: head-to-head can't separate them and no other
    tiebreaker is configured, so they keep the given (slot) order.
    """
    matches = [played(A, B, 1, 0), played(B, C, 1, 0), played(C, A, 1, 0)]
    table = {team: stats(3, 1, 1) for team in (A, B, C)}
    head_to_head_only = ranking([Tiebreaker.HEAD_TO_HEAD])
    assert order_by_ranking([C, A, B], table, matches, head_to_head_only, use_tiebreakers=True) == [
        C,
        A,
        B,
    ]


def test_without_tiebreakers_only_points_count() -> None:
    table = {A: stats(3, 0, 0), B: stats(3, 9, 0), D: stats(1, 0, 0)}
    order = order_by_ranking(
        [A, B, D], table, [], ranking(DEFAULT_TIEBREAKERS), use_tiebreakers=False
    )
    assert order == [A, B, D]


def test_tiebreakers_must_be_unique() -> None:
    with pytest.raises(ValueError, match="Each tiebreaker can only be used once"):
        RankingBody(
            win_points=Decimal("3"),
            draw_points=Decimal("1"),
            loss_points=Decimal("0"),
            add_score_points=False,
            position=0,
            tiebreakers=[Tiebreaker.HEAD_TO_HEAD, Tiebreaker.HEAD_TO_HEAD],
        )


def test_fair_play_fewest_card_points_first() -> None:
    inputs = [StageItemInputId(1), StageItemInputId(2), StageItemInputId(3)]
    equal = {input_id: stats(3, 2, 2) for input_id in inputs}
    data = TiebreakerData(card_points={StageItemInputId(1): 4, StageItemInputId(2): 1})
    order = order_by_ranking(
        inputs, equal, [], ranking([Tiebreaker.FAIR_PLAY]), use_tiebreakers=True, data=data
    )
    # No cards is best, then 1 point, then 4
    assert order == [StageItemInputId(3), StageItemInputId(2), StageItemInputId(1)]


def test_lots_entered_first_then_fixed_random_order() -> None:
    inputs = [StageItemInputId(i) for i in range(1, 6)]
    equal = {input_id: stats(3, 2, 2) for input_id in inputs}
    lots = ranking([Tiebreaker.LOTS])

    def order(data: TiebreakerData) -> list[StageItemInputId]:
        return order_by_ranking(inputs, equal, [], lots, use_tiebreakers=True, data=data)

    # Without entered lots: random, but the same every time for the same group
    assert order(TiebreakerData(lots_seed=7)) == order(TiebreakerData(lots_seed=7))
    assert sorted(order(TiebreakerData(lots_seed=7))) == inputs
    assert len({tuple(order(TiebreakerData(lots_seed=seed))) for seed in range(20)}) > 1
    # Entered lots win, lowest first, ahead of the teams without one
    entered = TiebreakerData(
        lot_numbers={StageItemInputId(4): 2, StageItemInputId(2): 1}, lots_seed=7
    )
    assert order(entered)[:2] == [StageItemInputId(2), StageItemInputId(4)]
