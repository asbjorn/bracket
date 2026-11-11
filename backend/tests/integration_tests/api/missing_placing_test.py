import pytest

from bracket.database import database
from bracket.models.db.stage_item_inputs import (
    StageItemInputEmpty,
    StageItemInputFinal,
    StageItemInputTentative,
)
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.teams import get_teams_with_members
from bracket.utils.http import HTTPMethod
from bracket.utils.types import JsonDict, assert_some
from tests.integration_tests.api.cup_setup_test import J14, delete_cup
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
from tests.integration_tests.models import AuthContext


@pytest.mark.asyncio(loop_scope="session")
async def test_playoffs_start_with_a_group_place_left_empty(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """
    7 teams in two groups of 4: one place stays empty. The empty place is not ranked, and the
    playoffs start anyway; the slot for "4. in the short group" simply gets no team.
    """
    tournament_id = auth_context.tournament.id
    try:
        body: JsonDict = {"classes": [J14], "time_windows": []}
        assert (
            await send_tournament_request(HTTPMethod.POST, "cup_setup", auth_context, json=body)
            == SUCCESS_RESPONSE
        )
        group_stage, _playoff_stage = sorted(
            await get_full_tournament_details(tournament_id), key=lambda stage: stage.id
        )
        category_id = assert_some(group_stage.category_id)
        names = "\n".join(f"Lag {index}" for index in range(1, 8))
        assert (
            await send_tournament_request(
                HTTPMethod.POST,
                "teams_multi",
                auth_context,
                json={"names": names, "active": True, "category_id": category_id},
            )
            == SUCCESS_RESPONSE
        )
        teams = await get_teams_with_members(tournament_id, category_id=category_id)
        draw = await send_tournament_request(
            HTTPMethod.POST,
            f"stages/{group_stage.id}/draw",
            auth_context,
            json={"pots": [[team.id for team in teams]], "seed": 1},
        )
        assert len(draw["data"]) == 7

        # Play every group match that has two teams: the first slot always wins 2-0
        [stage] = [
            s for s in await get_full_tournament_details(tournament_id) if s.id == group_stage.id
        ]
        for item in stage.stage_items:
            for round_ in item.rounds:
                for match in round_.matches:
                    await database.execute(
                        "UPDATE matches SET stage_item_input1_score = 2, "
                        "stage_item_input2_score = 0, played = true WHERE id = :id",
                        values={"id": match.id},
                    )
        response = await send_tournament_request(
            HTTPMethod.POST,
            "stages/activate",
            auth_context,
            json={"direction": "next", "category_id": category_id},
        )
        assert response == SUCCESS_RESPONSE

        stages = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        playoff_inputs = [input_ for item in stages[1].stage_items for input_ in item.inputs]
        filled = [i for i in playoff_inputs if isinstance(i, StageItemInputFinal)]
        unfilled = [
            i
            for i in playoff_inputs
            if isinstance(i, StageItemInputTentative | StageItemInputEmpty)
        ]
        # 8 playoff slots, 7 teams: exactly one slot (4th of the group with 3 teams) is empty
        assert (len(filled), len(unfilled)) == (7, 1)
        assert len({i.team_id for i in filled}) == 7
    finally:
        await delete_cup(auth_context)
