from decimal import Decimal

from heliclockter import datetime_utc

from bracket.logic.ranking.cross_group import rank_teams_at_placing
from bracket.logic.ranking.statistics import TeamStatistics
from bracket.models.db.stage_item import StageType
from bracket.models.db.util import StageItemWithRounds, StageWithStageItems
from bracket.utils.id_types import StageId, StageItemId, StageItemInputId, TournamentId

NOW = datetime_utc.now()


def group(group_id: int, name: str, team_count: int) -> StageItemWithRounds:
    return StageItemWithRounds(
        id=StageItemId(group_id),
        stage_id=StageId(1),
        name=name,
        created=NOW,
        type=StageType.ROUND_ROBIN,
        team_count=team_count,
        ranking_id=None,
        type_name="",
        inputs=[],
        rounds=[],
    )


def stats(
    wins: int, draws: int, losses: int, points: int, scored: int, conceded: int
) -> TeamStatistics:
    return TeamStatistics(
        wins=wins,
        draws=draws,
        losses=losses,
        points=Decimal(points),
        goals_for=scored,
        goals_against=conceded,
    )


def test_best_third_placed_teams_per_match() -> None:
    """
    Group C has 3 teams, so its third played only 2 matches: per match it did best.
    Groups A and B are equal per match, so A comes first (group order).
    """
    stage = StageWithStageItems(
        id=StageId(1),
        tournament_id=TournamentId(1),
        name="Groups",
        created=NOW,
        is_active=True,
        stage_items=[group(2, "Group B", 4), group(1, "Group A", 4), group(3, "Group C", 3)],
    )
    filler = (StageItemInputId(0), stats(0, 0, 0, 0, 0, 0))
    rankings = {
        StageItemId(1): [filler, filler, (StageItemInputId(13), stats(1, 1, 1, 4, 3, 3)), filler],
        StageItemId(2): [filler, filler, (StageItemInputId(23), stats(1, 1, 1, 4, 3, 3)), filler],
        # 3 points in 2 matches (1.5 per match) beats 4 points in 3 matches (1.33 per match)
        StageItemId(3): [filler, filler, (StageItemInputId(33), stats(1, 0, 1, 3, 2, 2))],
    }

    assert rank_teams_at_placing(stage, 3, rankings) == [33, 13, 23]
    # Group C has no fourth team
    assert rank_teams_at_placing(stage, 4, rankings) == [0, 0]
