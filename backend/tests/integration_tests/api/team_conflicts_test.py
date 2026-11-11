import itertools

import pytest

from bracket.models.db.stage_item_inputs import StageItemInputFinal
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.http import HTTPMethod
from bracket.utils.id_types import TeamId
from tests.integration_tests.api.cup_setup_test import delete_cup
from tests.integration_tests.api.score_links_test import set_up_playable_cup
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
from tests.integration_tests.models import AuthContext


async def overlapping_team_pairs(auth_context: AuthContext) -> set[tuple[TeamId, TeamId]]:
    """Pairs of teams that play at overlapping times (match plus margin)."""
    stages = await get_full_tournament_details(auth_context.tournament.id)
    team_of_input = {
        input_.id: input_.team_id
        for stage in stages
        for item in stage.stage_items
        for input_ in item.inputs
        if isinstance(input_, StageItemInputFinal)
    }
    matches = [
        match
        for stage in stages
        for item in stage.stage_items
        for round_ in item.rounds
        for match in round_.matches
        if match.start_time is not None
    ]
    pairs: set[tuple[TeamId, TeamId]] = set()
    for first, second in itertools.combinations(matches, 2):
        assert first.start_time is not None and second.start_time is not None
        end1 = first.start_time.timestamp() + 60 * (first.duration_minutes + first.margin_minutes)
        end2 = second.start_time.timestamp() + 60 * (
            second.duration_minutes + second.margin_minutes
        )
        if first.start_time.timestamp() < end2 and second.start_time.timestamp() < end1:
            for a in (first.stage_item_input1_id, first.stage_item_input2_id):
                for b in (second.stage_item_input1_id, second.stage_item_input2_id):
                    if a in team_of_input and b in team_of_input:
                        team_a, team_b = team_of_input[a], team_of_input[b]
                        pairs.add((min(team_a, team_b), max(team_a, team_b)))
    return pairs


@pytest.mark.asyncio(loop_scope="session")
async def test_teams_that_share_coaches_never_overlap(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    try:
        team_ids = await set_up_playable_cup(auth_context)
        brann, lyn, fana = team_ids["Brann"], team_ids["Lyn"], team_ids["Fana"]
        # Without constraints, two courts mean teams of different groups play at the same time
        assert len(await overlapping_team_pairs(auth_context)) > 0

        others = [team_id for name, team_id in team_ids.items() if name != "Brann"]
        response = await send_tournament_request(
            HTTPMethod.PUT, f"teams/{brann}/conflicts", auth_context, json={"team_ids": others}
        )
        assert response == SUCCESS_RESPONSE
        conflicts = await send_tournament_request(HTTPMethod.GET, "team_conflicts", auth_context)
        assert len(conflicts["data"]) == 5

        # A club whose teams never play at the same time
        club = await send_tournament_request(
            HTTPMethod.POST,
            "participating_clubs",
            auth_context,
            json={"name": "Bergen", "team_ids": [lyn, fana], "no_overlap": True},
        )
        assert "data" in club, club

        plan = await send_tournament_request(HTTPMethod.POST, "schedule/apply", auth_context)
        assert plan["data"]["unscheduled_match_ids"] == []
        overlaps = await overlapping_team_pairs(auth_context)
        assert not any(brann in pair for pair in overlaps), overlaps
        assert (min(lyn, fana), max(lyn, fana)) not in overlaps
        issues = await send_tournament_request(HTTPMethod.GET, "schedule/issues", auth_context)
        assert issues["data"] == []

        # Clearing the conflicts again
        await send_tournament_request(
            HTTPMethod.PUT, f"teams/{brann}/conflicts", auth_context, json={"team_ids": []}
        )
        conflicts = await send_tournament_request(HTTPMethod.GET, "team_conflicts", auth_context)
        assert conflicts["data"] == []
    finally:
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_team_conflicts_only_within_the_cup(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    try:
        team_ids = await set_up_playable_cup(auth_context)
        response = await send_tournament_request(
            HTTPMethod.PUT,
            f"teams/{team_ids['Brann']}/conflicts",
            auth_context,
            json={"team_ids": [999999]},
        )
        assert response == {"detail": "Some of the teams don't exist in this tournament"}
    finally:
        await delete_cup(auth_context)
