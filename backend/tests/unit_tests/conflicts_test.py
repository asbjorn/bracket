from datetime import timedelta

import pytest

from bracket.logic.planning.conflicts import get_conflicting_matches, matches_overlap
from bracket.models.db.util import StageWithStageItems
from bracket.utils.dummy_records import DUMMY_MOCK_TIME
from bracket.utils.id_types import StageId, TournamentId
from tests.integration_tests.mocks import MOCK_NOW
from tests.unit_tests.mocks import (
    get_2_definitive_matches_mock,
    get_one_round_with_two_definitive_matches,
    get_stage_item_inputs_mock,
    get_stage_item_mock,
)


def test_get_conflicting_matches_conflicts_to_set() -> None:
    """
    Test `get_conflicting_matches` returns the right conflicts to set
    """
    tournament_id = TournamentId(-1)
    stage_item_inputs = get_stage_item_inputs_mock(tournament_id)
    match1, match2 = get_2_definitive_matches_mock(stage_item_inputs)
    rounds = get_one_round_with_two_definitive_matches(match1, match2)
    stage_item = StageWithStageItems(
        id=StageId(-1),
        tournament_id=tournament_id,
        name="",
        created=MOCK_NOW,
        is_active=False,
        stage_items=[get_stage_item_mock(stage_item_inputs, [rounds])],
    )

    assert get_conflicting_matches([stage_item]) == ({-1: [True, False], -2: [True, False]}, set())


def get_stage_with_two_matches(match1_start_offset: timedelta) -> StageWithStageItems:
    """
    Both mocked matches take 90 minutes plus 15 minutes margin and share a team.
    Match 2 starts at `DUMMY_MOCK_TIME`, match 1 starts `match1_start_offset` later.
    """
    tournament_id = TournamentId(-1)
    stage_item_inputs = get_stage_item_inputs_mock(tournament_id)
    match1, match2 = get_2_definitive_matches_mock(
        stage_item_inputs, DUMMY_MOCK_TIME + match1_start_offset
    )
    rounds = get_one_round_with_two_definitive_matches(match1, match2)
    return StageWithStageItems(
        id=StageId(-1),
        tournament_id=tournament_id,
        name="",
        created=MOCK_NOW,
        is_active=False,
        stage_items=[get_stage_item_mock(stage_item_inputs, [rounds])],
    )


@pytest.mark.parametrize(
    "match1_start_offset",
    [
        pytest.param(timedelta(hours=1), id="partial overlap, match 1 later"),
        pytest.param(-timedelta(hours=1), id="partial overlap, match 1 earlier"),
        pytest.param(timedelta(minutes=104), id="one minute overlap"),
        pytest.param(timedelta(0), id="same start"),
    ],
)
def test_get_conflicting_matches_overlapping(match1_start_offset: timedelta) -> None:
    """
    Test `get_conflicting_matches` detects any overlap, not only identical start times
    """
    stage = get_stage_with_two_matches(match1_start_offset)
    assert get_conflicting_matches([stage]) == ({-1: [True, False], -2: [True, False]}, set())


@pytest.mark.parametrize(
    "match1_start_offset",
    [
        pytest.param(timedelta(minutes=105), id="directly after, including margin"),
        pytest.param(-timedelta(minutes=105), id="directly before, including margin"),
        pytest.param(timedelta(hours=3), id="much later"),
    ],
)
def test_get_conflicting_matches_conflicts_to_clear(match1_start_offset: timedelta) -> None:
    """
    Test `get_conflicting_matches` returns the right conflicts to clear
    """
    stage = get_stage_with_two_matches(match1_start_offset)
    assert get_conflicting_matches([stage]) == ({}, {-1, -2})


def test_matches_overlap_containment() -> None:
    """
    A match fully inside another one overlaps, regardless of argument order
    """
    stage_item_inputs = get_stage_item_inputs_mock(TournamentId(-1))
    long_match, _ = get_2_definitive_matches_mock(stage_item_inputs)
    short_match = long_match.model_copy(
        update={
            "start_time": DUMMY_MOCK_TIME + timedelta(minutes=30),
            "duration_minutes": 10,
            "margin_minutes": 0,
        }
    )
    assert matches_overlap(long_match, short_match)
    assert matches_overlap(short_match, long_match)
