import pytest

from bracket.database import database
from bracket.schema import tournaments
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.http import HTTPMethod
from bracket.utils.types import JsonDict
from tests.integration_tests.api.cup_setup_test import delete_cup
from tests.integration_tests.api.score_links_test import set_up_playable_cup
from tests.integration_tests.api.shared import send_tournament_request
from tests.integration_tests.models import AuthContext


@pytest.mark.asyncio(loop_scope="session")
async def test_archived_tournament_can_not_be_changed(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    try:
        teams = await set_up_playable_cup(auth_context)
        [stage] = await get_full_tournament_details(tournament_id)
        group = stage.stage_items[0]
        await database.execute(
            tournaments.update().where(tournaments.c.id == tournament_id),
            values={"status": "ARCHIVED"},
        )
        archived = {"detail": "Can't update archived tournament"}
        changes: list[tuple[HTTPMethod, str, JsonDict | None]] = [
            (HTTPMethod.PUT, f"teams/{teams['Brann']}/check_in", {"checked_in": True}),
            (
                HTTPMethod.POST,
                "stage_items",
                {"stage_id": stage.id, "type": "ROUND_ROBIN", "team_count": 4},
            ),
            (HTTPMethod.DELETE, f"stage_items/{group.id}", None),
            (HTTPMethod.DELETE, "courts/1/split?unschedule_matches=true", None),
        ]
        for method, endpoint, body in changes:
            response = await send_tournament_request(method, endpoint, auth_context, json=body)
            assert response == archived, endpoint
    finally:
        await database.execute(
            tournaments.update().where(tournaments.c.id == tournament_id),
            values={"status": "OPEN"},
        )
        await delete_cup(auth_context)
