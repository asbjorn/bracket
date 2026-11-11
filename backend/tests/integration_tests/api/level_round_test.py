import pytest

from bracket.models.db.stage_item_inputs import StageItemInputFinal
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.cup_setup_test import delete_cup
from tests.integration_tests.api.score_links_test import set_up_playable_cup
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
from tests.integration_tests.models import AuthContext


@pytest.mark.asyncio(loop_scope="session")
async def test_level_split_round_in_a_childrens_class(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """G10 (hidden results): a second round of groups composed by hand."""
    tournament_id = auth_context.tournament.id
    try:
        team_ids = await set_up_playable_cup(auth_context)
        [group_stage] = await get_full_tournament_details(tournament_id)
        ids = list(team_ids.values())
        body = {
            "stage_name": "Runde 2",
            "groups": [
                {"name": "Nivå 1", "team_ids": ids[:3]},
                {"name": "Nivå 2", "team_ids": ids[3:]},
            ],
        }
        response = await send_tournament_request(
            HTTPMethod.POST,
            f"categories/{group_stage.category_id}/level_round",
            auth_context,
            json=body,
        )
        assert response == SUCCESS_RESPONSE
        stages = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        level_stage = stages[-1]
        assert level_stage.name == "Runde 2" and level_stage.category_id == group_stage.category_id
        for item, expected in zip(
            sorted(level_stage.stage_items, key=lambda i: i.name), (ids[:3], ids[3:]), strict=True
        ):
            assert [
                i.team_id for i in sorted(item.inputs, key=lambda i: i.slot)
            ] == expected and all(isinstance(i, StageItemInputFinal) for i in item.inputs)
            assert sum(len(r.matches) for r in item.rounds) == 3
        # The next stage can be started although the class's results are hidden
        response = await send_tournament_request(
            HTTPMethod.POST,
            "stages/activate",
            auth_context,
            json={"direction": "next", "category_id": group_stage.category_id},
        )
        assert response == SUCCESS_RESPONSE

        bad = body | {"groups": [{"name": "A", "team_ids": [ids[0], ids[0]]}]}
        response = await send_tournament_request(
            HTTPMethod.POST,
            f"categories/{group_stage.category_id}/level_round",
            auth_context,
            json=bad,
        )
        assert "A team can only be in one group" in str(response)
    finally:
        await delete_cup(auth_context)
