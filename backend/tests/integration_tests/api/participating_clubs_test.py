import pytest

from bracket.database import database
from bracket.routes.registrations import public_sign_ups
from bracket.schema import tournaments
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.dummy_records import DUMMY_MOCK_TIME, DUMMY_TEAM1, DUMMY_TOURNAMENT
from bracket.utils.http import HTTPMethod
from bracket.utils.types import JsonDict
from tests.integration_tests.api.cup_setup_test import delete_cup
from tests.integration_tests.api.draw_test import set_up_classes
from tests.integration_tests.api.registration_test import create_class, public_post, sign_up
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import inserted_team, inserted_tournament

ENDPOINT = "participating_clubs"


async def get_clubs(auth_context: AuthContext) -> list[JsonDict]:
    response = await send_tournament_request(HTTPMethod.GET, ENDPOINT, auth_context)
    return list(response["data"])


async def create_club(auth_context: AuthContext, body: JsonDict) -> JsonDict:
    return await send_tournament_request(HTTPMethod.POST, ENDPOINT, auth_context, json=body)


def team_names(club: JsonDict) -> list[str]:
    return sorted(team["name"] for team in club["teams"])


@pytest.mark.asyncio(loop_scope="session")
async def test_club_wizard_and_membership(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    try:
        team_ids = await set_up_classes(auth_context)
        classes = await send_tournament_request(HTTPMethod.GET, "categories", auth_context)
        g10 = min(c["id"] for c in classes["data"])

        # Wizard: two existing teams and one new team at once
        created = await create_club(
            auth_context,
            {
                "name": "Brann",
                "team_ids": [team_ids["Brann 1"], team_ids["Brann 2"]],
                "new_teams": [{"name": "Brann 3", "category_id": g10}],
            },
        )
        brann_id = created["data"]
        [brann] = await get_clubs(auth_context)
        assert (brann["id"], brann["name"]) == (brann_id, "Brann")
        assert team_names(brann) == ["Brann 1", "Brann 2", "Brann 3"]
        assert {team["category_id"] for team in brann["teams"]} == {g10}

        # Same name (any case) twice, a team of another club, and unknown ids are refused
        duplicate = await create_club(auth_context, {"name": "BRANN "})
        assert duplicate == {"detail": "A club with this name already takes part in this cup"}
        taken = await create_club(auth_context, {"name": "Lyn", "team_ids": [team_ids["Brann 1"]]})
        assert taken == {"detail": "Some of the teams already belong to another club"}
        unknown = await create_club(auth_context, {"name": "Lyn", "team_ids": [999999]})
        assert unknown == {"detail": "Some of the teams don't exist in this tournament"}
        bad_class = await create_club(
            auth_context, {"name": "Lyn", "new_teams": [{"name": "Lyn", "category_id": 999999}]}
        )
        assert bad_class == {"detail": "Some of the classes don't exist in this tournament"}
        control = await create_club(auth_context, {"name": "Lyn\r\nBcc: x@example.org"})
        assert "control characters" in str(control)
        assert len(await get_clubs(auth_context)) == 1

        # Update sets exactly the teams: Brann 3 leaves, Lyn (no club) joins
        response = await send_tournament_request(
            HTTPMethod.PUT,
            f"{ENDPOINT}/{brann_id}",
            auth_context,
            json={
                "name": "SK Brann",
                "team_ids": [team_ids["Brann 1"], team_ids["Brann 2"], team_ids["Lyn"]],
            },
        )
        assert response == SUCCESS_RESPONSE
        [brann] = await get_clubs(auth_context)
        assert brann["name"] == "SK Brann"
        assert team_names(brann) == ["Brann 1", "Brann 2", "Lyn"]

        # A team's own edit form can set the club; a club of another tournament is refused
        teams = await send_tournament_request(HTTPMethod.GET, "teams", auth_context)
        fana = next(t for t in teams["data"]["teams"] if t["name"] == "Fana")
        assert fana["club_id"] is None
        edit = {"name": "Fana", "active": True, "player_ids": [], "category_id": g10}
        response = await send_tournament_request(
            HTTPMethod.PUT, f"teams/{fana['id']}", auth_context, json=edit | {"club_id": brann_id}
        )
        assert response["data"]["club_id"] == brann_id
        response = await send_tournament_request(
            HTTPMethod.PUT, f"teams/{fana['id']}", auth_context, json=edit | {"club_id": 999999}
        )
        assert "Could not find ParticipatingClub" in str(response)

        # Deleting the club keeps its teams
        response = await send_tournament_request(
            HTTPMethod.DELETE, f"{ENDPOINT}/{brann_id}", auth_context
        )
        assert response == SUCCESS_RESPONSE
        assert await get_clubs(auth_context) == []
        teams = await send_tournament_request(HTTPMethod.GET, "teams", auth_context)
        names = {t["name"]: t["club_id"] for t in teams["data"]["teams"]}
        assert names["Brann 3"] is None
        assert names["Fana"] is None
    finally:
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_clubs_of_other_tournaments(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """Teams of another tournament can't be added, and archived cups can't be changed."""
    tournament_id = auth_context.tournament.id
    try:
        async with (
            inserted_tournament(
                DUMMY_TOURNAMENT.model_copy(
                    update={"club_id": auth_context.club.id, "dashboard_endpoint": None}
                )
            ) as other_tournament,
            inserted_team(
                DUMMY_TEAM1.model_copy(
                    update={"tournament_id": other_tournament.id, "created": DUMMY_MOCK_TIME}
                )
            ) as stranger,
        ):
            response = await create_club(auth_context, {"name": "Os", "team_ids": [stranger.id]})
            assert response == {"detail": "Some of the teams don't exist in this tournament"}

        created = await create_club(auth_context, {"name": "Os"})
        await database.execute(
            tournaments.update().where(tournaments.c.id == tournament_id),
            values={"status": "ARCHIVED"},
        )
        archived = {"detail": "Can't update archived tournament"}
        assert await create_club(auth_context, {"name": "Fana"}) == archived
        response = await send_tournament_request(
            HTTPMethod.DELETE, f"{ENDPOINT}/{created['data']}", auth_context
        )
        assert response == archived
    finally:
        await database.execute(
            tournaments.update().where(tournaments.c.id == tournament_id),
            values={"status": "OPEN"},
        )
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_sign_up_finds_or_creates_the_club(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    public_sign_ups.hits.clear()
    try:
        await database.execute(
            tournaments.update().where(tournaments.c.id == tournament_id),
            values={"dashboard_public": True},
        )
        category_id = await create_class(auth_context, {"registration_open": True})
        for team, club in [("Brann 1", "Brann"), ("Brann 2", " brann "), ("Lyn", None)]:
            response = await public_post(tournament_id, sign_up(category_id, team, club_name=club))
            assert response["data"]["registration_status"] == "REGISTERED", response
        [brann] = await get_clubs(auth_context)
        assert brann["name"] == "Brann"
        assert team_names(brann) == ["Brann 1", "Brann 2"]

        registrations = await send_tournament_request(HTTPMethod.GET, "registrations", auth_context)
        clubs = {r["team_name"]: r["club_name"] for r in registrations["data"]}
        assert clubs == {"Brann 1": "Brann", "Brann 2": "Brann", "Lyn": None}
    finally:
        public_sign_ups.hits.clear()
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_draw_keeps_a_club_apart(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """Fana and Os are made one club: they always end up in different groups."""
    tournament_id = auth_context.tournament.id
    try:
        team_ids = await set_up_classes(auth_context)
        await create_club(
            auth_context, {"name": "Vest", "team_ids": [team_ids["Fana"], team_ids["Os"]]}
        )
        stages = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        for seed in range(6):
            response = await send_tournament_request(
                HTTPMethod.POST,
                f"stages/{stages[0].id}/draw",
                auth_context,
                json={"pots": [list(team_ids.values())], "seed": seed},
            )
            groups = {p["team_id"]: p["stage_item_id"] for p in response["data"]}
            assert groups[team_ids["Fana"]] != groups[team_ids["Os"]]
            # Empty the groups again for the next seed
            await database.execute(
                """
                UPDATE stage_item_inputs SET team_id = NULL
                WHERE tournament_id = :tournament_id AND team_id IS NOT NULL
                """,
                values={"tournament_id": tournament_id},
            )
    finally:
        await delete_cup(auth_context)
