from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest

from bracket.database import database
from bracket.models.db.user_x_club import UserXClubRelation
from bracket.schema import users_x_clubs
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.dummy_records import DUMMY_TOURNAMENT
from bracket.utils.http import HTTPMethod
from bracket.utils.types import JsonDict
from tests.integration_tests.api.cup_setup_test import G10, delete_cup
from tests.integration_tests.api.shared import send_auth_request, send_tournament_request
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import inserted_tournament

OWNER_REQUIRED = {"detail": "Only an owner of the club can do this"}


@asynccontextmanager
async def as_collaborator(auth_context: AuthContext) -> AsyncIterator[None]:
    async def set_relation(relation: UserXClubRelation) -> None:
        await database.execute(
            users_x_clubs.update().where(users_x_clubs.c.id == auth_context.user_x_club.id),
            values={"relation": relation.value},
        )

    await set_relation(UserXClubRelation.COLLABORATOR)
    try:
        yield
    finally:
        await set_relation(UserXClubRelation.OWNER)


@pytest.mark.asyncio(loop_scope="session")
async def test_collaborator_cannot_delete_or_rename(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    club_id = auth_context.club.id
    async with as_collaborator(auth_context):
        tournament = f"tournaments/{auth_context.tournament.id}"
        assert (
            await send_auth_request(HTTPMethod.DELETE, tournament, auth_context) == OWNER_REQUIRED
        )
        assert (
            await send_auth_request(HTTPMethod.DELETE, f"clubs/{club_id}", auth_context)
            == OWNER_REQUIRED
        )
        assert (
            await send_auth_request(
                HTTPMethod.PUT, f"clubs/{club_id}", auth_context, json={"name": "Renamed"}
            )
            == OWNER_REQUIRED
        )
        # Running the tournament is allowed
        response = await send_tournament_request(
            HTTPMethod.POST, "courts", auth_context, json={"name": "Bane 9"}
        )
        assert "data" in response
        await send_tournament_request(
            HTTPMethod.DELETE, f"courts/{response['data']['id']}", auth_context
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_owner_can_rename_club(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    club = auth_context.club
    response = await send_auth_request(
        HTTPMethod.PUT, f"clubs/{club.id}", auth_context, json={"name": club.name}
    )
    assert response["data"]["name"] == club.name


@pytest.mark.asyncio(loop_scope="session")
async def test_matches_and_rounds_only_via_their_own_tournament(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """Regression: the tournament filter of the match and round lookups was ignored."""
    body: JsonDict = {"classes": [G10], "time_windows": []}
    try:
        await send_tournament_request(HTTPMethod.POST, "cup_setup", auth_context, json=body)
        [stage] = await get_full_tournament_details(auth_context.tournament.id)
        round_ = stage.stage_items[0].rounds[0]
        match = round_.matches[0]
        async with inserted_tournament(
            DUMMY_TOURNAMENT.model_copy(
                update={"club_id": auth_context.club.id, "dashboard_endpoint": "other-cup"}
            )
        ) as other:
            update = {"round_id": round_.id, "stage_item_input1_score": 5, "played": True}
            response = await send_auth_request(
                HTTPMethod.PUT,
                f"tournaments/{other.id}/matches/{match.id}",
                auth_context,
                json=update | {"result_type": "NORMAL", "court_id": None},
            )
            assert response == {"detail": f"Could not find match with id {match.id}"}
            response = await send_auth_request(
                HTTPMethod.DELETE, f"tournaments/{other.id}/matches/{match.id}", auth_context
            )
            assert response == {"detail": f"Could not find match with id {match.id}"}
            response = await send_auth_request(
                HTTPMethod.DELETE, f"tournaments/{other.id}/rounds/{round_.id}", auth_context
            )
            assert response == {"detail": f"Could not find round with id {round_.id}"}
    finally:
        await delete_cup(auth_context)
