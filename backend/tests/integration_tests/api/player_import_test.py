import pytest

from bracket.database import database
from bracket.schema import players, players_x_teams, users
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.cup_setup_test import delete_cup
from tests.integration_tests.api.score_links_test import set_up_playable_cup
from tests.integration_tests.api.shared import send_tournament_request
from tests.integration_tests.models import AuthContext

LONG_NAME = "Anne-Marie Kristine Østby-Haugland de la Fontaine Bjørnstad Sørensen Ødegård Nilsen"


async def delete_players(auth_context: AuthContext) -> None:
    tournament_id = auth_context.tournament.id
    await database.execute(
        "DELETE FROM players_x_teams WHERE player_id IN "
        "(SELECT id FROM players WHERE tournament_id = :id)",
        values={"id": tournament_id},
    )
    await database.execute(players.delete().where(players.c.tournament_id == tournament_id))


@pytest.mark.asyncio(loop_scope="session")
async def test_import_players(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    try:
        teams = await set_up_playable_cup(auth_context)
        rows = [
            {"name": "Ola Nordmann", "team_id": teams["Brann"]},
            {"name": LONG_NAME, "team_id": teams["Brann"]},
            {"name": "Kari  Nordmann"},
            {"name": "ola nordmann", "team_id": teams["Lyn"]},  # Twice in the file
        ]
        response = await send_tournament_request(
            HTTPMethod.POST, "players_import", auth_context, json={"rows": rows}
        )
        # The test cup allows players in several teams
        assert response["data"] == {
            "created": 3,
            "added_to_team": 0,
            "skipped": ["ola nordmann"],
            "not_added_to_team": [],
        }
        names = {
            row["name"]
            for row in await database.fetch_all(
                players.select().where(players.c.tournament_id == tournament_id)
            )
        }
        assert names == {"Ola Nordmann", LONG_NAME, "Kari Nordmann"}
        links = await database.fetch_all(players_x_teams.select())
        brann_and_lyn = {row["team_id"] for row in links}
        # Ola: Brann (first row) and Lyn (the duplicate row still puts him on Lyn)
        assert brann_and_lyn >= {teams["Brann"], teams["Lyn"]}

        # Importing again: everyone exists; Kari is put on Fana
        again = await send_tournament_request(
            HTTPMethod.POST,
            "players_import",
            auth_context,
            json={"rows": [{"name": "KARI NORDMANN", "team_id": teams["Fana"]}]},
        )
        assert again["data"] == {
            "created": 0,
            "added_to_team": 1,
            "skipped": ["KARI NORDMANN"],
            "not_added_to_team": [],
        }

        # A cup where a player can only be on one team: Ola isn't put on Fana
        await database.execute(
            "UPDATE tournaments SET players_can_be_in_multiple_teams = false WHERE id = :id",
            values={"id": tournament_id},
        )
        one_team = await send_tournament_request(
            HTTPMethod.POST,
            "players_import",
            auth_context,
            json={"rows": [{"name": "Ola Nordmann", "team_id": teams["Fana"]}]},
        )
        assert one_team["data"]["not_added_to_team"] == ["Ola Nordmann"]
        await database.execute(
            "UPDATE tournaments SET players_can_be_in_multiple_teams = true WHERE id = :id",
            values={"id": tournament_id},
        )

        # Names longer than 100 characters, other cups' teams and too many rows are refused
        too_long = await send_tournament_request(
            HTTPMethod.POST, "players_import", auth_context, json={"rows": [{"name": "x" * 101}]}
        )
        assert "at most 100 characters" in str(too_long)
        other_team = await send_tournament_request(
            HTTPMethod.POST,
            "players_import",
            auth_context,
            json={"rows": [{"name": "Per", "team_id": 999999}]},
        )
        assert other_team == {"detail": "Some of the teams don't exist in this cup"}
        many = await send_tournament_request(
            HTTPMethod.POST,
            "players_import",
            auth_context,
            json={"rows": [{"name": f"P{i}"} for i in range(2001)]},
        )
        assert "at most 2000" in str(many)
        # The old text field also refuses too long names with a clear message
        multi = await send_tournament_request(
            HTTPMethod.POST,
            "players_multi",
            auth_context,
            json={"names": "Per\n" + "y" * 101, "active": True},
        )
        assert multi["detail"].startswith("Names can have at most 100 characters")
    finally:
        await database.execute(
            "UPDATE tournaments SET players_can_be_in_multiple_teams = true WHERE id = :id",
            values={"id": tournament_id},
        )
        await delete_players(auth_context)
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_import_respects_subscription(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    user_id = auth_context.user.id
    await database.execute(
        users.update().where(users.c.id == user_id), values={"account_type": "DEMO"}
    )
    try:
        response = await send_tournament_request(
            HTTPMethod.POST,
            "players_import",
            auth_context,
            json={"rows": [{"name": f"Spiller {i}"} for i in range(17)]},
        )
        assert response == {"detail": "Your `DEMO` subscription allows a maximum of 16 players."}
        count = await database.fetch_val(
            "SELECT count(*) FROM players WHERE tournament_id = :id",
            values={"id": auth_context.tournament.id},
        )
        assert count == 0
    finally:
        await database.execute(
            users.update().where(users.c.id == user_id), values={"account_type": "REGULAR"}
        )
        await delete_players(auth_context)
