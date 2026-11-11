from bracket.logic.ranking.elimination import get_inputs_to_update_in_subsequent_elimination_rounds
from bracket.models.db.match import MatchResultType
from bracket.utils.id_types import (
    RoundId,
    TournamentId,
)
from tests.unit_tests.mocks import (
    get_2_definitive_and_2_tentative_matches_mock,
    get_one_round_with_two_definitive_matches,
    get_stage_item_inputs_mock,
    get_stage_item_mock,
    get_two_round_with_one_tentative_match_each,
)


def test_elimination_input_updates() -> None:
    tournament_id = TournamentId(-1)
    stage_item_inputs = get_stage_item_inputs_mock(tournament_id)
    matches = get_2_definitive_and_2_tentative_matches_mock(stage_item_inputs)
    rounds = [
        get_one_round_with_two_definitive_matches(matches[0], matches[1]),
        *get_two_round_with_one_tentative_match_each(matches[2], matches[3]),
    ]

    updates = get_inputs_to_update_in_subsequent_elimination_rounds(
        RoundId(-3),
        get_stage_item_mock(stage_item_inputs, rounds),
        {matches[0].id, matches[1].id},
    )

    assert updates == {
        matches[2].id: matches[2].model_copy(
            update={
                "stage_item_input1_id": stage_item_inputs[0].id,
                "stage_item_input2_id": stage_item_inputs[3].id,
                "stage_item_input1": stage_item_inputs[0],
                "stage_item_input2": stage_item_inputs[3],
            }
        ),
        matches[3].id: matches[3].model_copy(
            update={
                "stage_item_input1_id": stage_item_inputs[3].id,
                "stage_item_input2_id": stage_item_inputs[0].id,
                "stage_item_input1": stage_item_inputs[3],
                "stage_item_input2": stage_item_inputs[0],
            }
        ),
    }


def test_elimination_unplayed_match_has_no_winner_yet() -> None:
    """
    A live score (match not marked as played) must not send a team to the next round.
    """
    tournament_id = TournamentId(-1)
    stage_item_inputs = get_stage_item_inputs_mock(tournament_id)
    matches = get_2_definitive_and_2_tentative_matches_mock(stage_item_inputs)
    live_matches = (
        matches[0].model_copy(update={"played": False}),
        matches[1].model_copy(update={"played": False}),
    )
    rounds = [
        get_one_round_with_two_definitive_matches(*live_matches),
        *get_two_round_with_one_tentative_match_each(matches[2], matches[3]),
    ]

    updates = get_inputs_to_update_in_subsequent_elimination_rounds(
        RoundId(-3),
        get_stage_item_mock(stage_item_inputs, rounds),
        {matches[0].id, matches[1].id},
    )
    assert not updates


def test_elimination_penalty_shootout_decides() -> None:
    """
    Match 1 ends 1-1 and team 2 wins the penalty shootout 5-4, so it advances instead of team 1.
    """
    tournament_id = TournamentId(-1)
    stage_item_inputs = get_stage_item_inputs_mock(tournament_id)
    matches = get_2_definitive_and_2_tentative_matches_mock(stage_item_inputs)
    shootout = matches[0].model_copy(
        update={
            "stage_item_input1_score": 1,
            "stage_item_input2_score": 1,
            "result_type": MatchResultType.PENALTIES,
            "stage_item_input1_penalties": 4,
            "stage_item_input2_penalties": 5,
        }
    )
    rounds = [
        get_one_round_with_two_definitive_matches(shootout, matches[1]),
        *get_two_round_with_one_tentative_match_each(matches[2], matches[3]),
    ]

    updates = get_inputs_to_update_in_subsequent_elimination_rounds(
        RoundId(-3),
        get_stage_item_mock(stage_item_inputs, rounds),
        {matches[0].id, matches[1].id},
    )
    assert updates[matches[2].id].stage_item_input1 == stage_item_inputs[1]
