import pytest

from bracket.models.db.stage_item_inputs import StageItemInputFinal
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.teams import get_teams_with_members
from bracket.utils.http import HTTPMethod
from bracket.utils.id_types import TeamId
from bracket.utils.types import JsonDict, assert_some
from tests.integration_tests.api.cup_setup_test import G10, J14, delete_cup
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
from tests.integration_tests.models import AuthContext

TEAM_NAMES = ["Brann 1", "Brann 2", "Lyn", "Fana", "Os", "Nest-Sotra"]


async def set_up_classes(auth_context: AuthContext) -> dict[str, TeamId]:
    """G10 (two groups of 3) and J14 (two groups of 4); six G10 teams. Team ids by name."""
    body: JsonDict = {"classes": [G10, J14], "time_windows": []}
    response = await send_tournament_request(HTTPMethod.POST, "cup_setup", auth_context, json=body)
    assert response == SUCCESS_RESPONSE
    stages = await get_full_tournament_details(auth_context.tournament.id)
    g10_id = min(assert_some(stage.category_id) for stage in stages)
    response = await send_tournament_request(
        HTTPMethod.POST,
        "teams_multi",
        auth_context,
        json={"names": "\n".join(TEAM_NAMES), "active": True, "category_id": g10_id},
    )
    assert response == SUCCESS_RESPONSE
    teams = await get_teams_with_members(auth_context.tournament.id, category_id=g10_id)
    return {team.name: team.id for team in teams}


@pytest.mark.asyncio(loop_scope="session")
async def test_draw(startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext) -> None:
    tournament_id = auth_context.tournament.id
    try:
        team_ids = await set_up_classes(auth_context)
        [g10_stage, j14_stage, _] = sorted(
            await get_full_tournament_details(tournament_id), key=lambda stage: stage.id
        )
        pots = [[team_ids["Brann 1"], team_ids["Lyn"]], [team_ids[n] for n in TEAM_NAMES[2:]]]
        pots[1].remove(team_ids["Lyn"])
        pots[1].append(team_ids["Brann 2"])
        endpoint = f"stages/{g10_stage.id}/draw"

        response = await send_tournament_request(
            HTTPMethod.POST, endpoint, auth_context, json={"pots": pots, "seed": 1}
        )
        placements = response["data"]
        assert [p["team_id"] for p in placements[:2]] in (pots[0], pots[0][::-1])
        assert len(placements) == 6

        [stage] = [
            s for s in await get_full_tournament_details(tournament_id) if s.id == g10_stage.id
        ]
        group_of_team = {
            input_.team_id: item.name
            for item in stage.stage_items
            for input_ in item.inputs
            if isinstance(input_, StageItemInputFinal)
        }
        assert len(group_of_team) == 6
        # Same club apart, and one team of pot 1 per group
        assert group_of_team[team_ids["Brann 1"]] != group_of_team[team_ids["Brann 2"]]
        assert group_of_team[team_ids["Brann 1"]] != group_of_team[team_ids["Lyn"]]
        # The teams are in the matches now
        matches = [m for item in stage.stage_items for r in item.rounds for m in r.matches]
        assert all(m.stage_item_input1_id is not None for m in matches)

        # Drawn teams can't be drawn again, and the groups are full
        again = await send_tournament_request(
            HTTPMethod.POST, endpoint, auth_context, json={"pots": [[team_ids["Lyn"]]]}
        )
        assert again == {"detail": "Some of the teams are already in a group of this stage"}

        # Teams of another class can't be drawn into J14
        other = await send_tournament_request(
            HTTPMethod.POST,
            f"stages/{j14_stage.id}/draw",
            auth_context,
            json={"pots": [[team_ids["Lyn"]]]},
        )
        assert other == {"detail": "All teams must belong to the class of the stage"}
    finally:
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_draw_errors(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    try:
        team_ids = await set_up_classes(auth_context)
        stages = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        all_teams = list(team_ids.values())

        wrong_class = await send_tournament_request(
            HTTPMethod.POST, f"stages/{stages[2].id}/draw", auth_context, json={"pots": [all_teams]}
        )
        assert "All teams must belong to the class of the stage" in str(wrong_class)

        duplicate = await send_tournament_request(
            HTTPMethod.POST,
            f"stages/{stages[0].id}/draw",
            auth_context,
            json={"pots": [all_teams, all_teams[:1]]},
        )
        assert "A team can only be in one pot" in str(duplicate)

        missing = await send_tournament_request(
            HTTPMethod.POST, "stages/999999/draw", auth_context, json={"pots": [all_teams]}
        )
        assert missing == {"detail": "Could not find the stage"}
    finally:
        await delete_cup(auth_context)
