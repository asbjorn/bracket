import pytest

from bracket.database import database
from bracket.schema import jury_decisions, match_cards
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.http import HTTPMethod
from bracket.utils.types import JsonDict
from tests.integration_tests.api.cup_setup_test import G10, delete_cup
from tests.integration_tests.api.score_links_test import delete_score_links, set_up_playable_cup
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    send_request,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext

J16 = G10 | {"name": "J16", "age": 16}


async def clean_up(auth_context: AuthContext) -> None:
    tournament_id = auth_context.tournament.id
    await database.execute(
        jury_decisions.delete().where(jury_decisions.c.tournament_id == tournament_id)
    )
    await database.execute(match_cards.delete().where(match_cards.c.tournament_id == tournament_id))
    await delete_score_links(auth_context)
    await delete_cup(auth_context)


async def matches_of_team(auth_context: AuthContext, team_id: int) -> list[JsonDict]:
    """The team's matches in schedule order."""
    matches = [
        match
        for stage in await get_full_tournament_details(auth_context.tournament.id)
        for item in stage.stage_items
        for round_ in item.rounds
        for match in round_.matches
        if team_id
        in {
            getattr(match.stage_item_input1, "team_id", None),
            getattr(match.stage_item_input2, "team_id", None),
        }
    ]
    matches.sort(key=lambda m: (m.start_time, m.id))
    return [{"id": m.id, "start_time": m.start_time} for m in matches]


def red_card(team_id: int, player: str = "Ola Nordmann") -> JsonDict:
    return {"team_id": team_id, "player_name": player, "card_type": "RED", "minute": 12}


@pytest.mark.asyncio(loop_scope="session")
async def test_cards_and_suspensions(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    try:
        teams = await set_up_playable_cup(auth_context, J16)
        brann = teams["Brann"]
        first, second = await matches_of_team(auth_context, brann)

        response = await send_tournament_request(
            HTTPMethod.POST, f"matches/{first['id']}/cards", auth_context, json=red_card(brann)
        )
        card_id = response["data"]["id"]
        overview = (await send_tournament_request(HTTPMethod.GET, "discipline", auth_context))[
            "data"
        ]
        assert [(s["player_name"], s["match_ids"]) for s in overview["suspensions"]] == [
            ("Ola Nordmann", [second["id"]])
        ]

        # The jury lifts the suspension
        response = await send_tournament_request(
            HTTPMethod.POST,
            "jury_decisions",
            auth_context,
            json={"text": "Feil person", "card_id": card_id, "suspension_change": -1},
        )
        assert response == SUCCESS_RESPONSE
        overview = (await send_tournament_request(HTTPMethod.GET, "discipline", auth_context))[
            "data"
        ]
        assert overview["suspensions"] == []
        assert overview["decisions"][0]["decided_by"] == auth_context.user.id

        # A change needs a card
        response = await send_tournament_request(
            HTTPMethod.POST,
            "jury_decisions",
            auth_context,
            json={"text": "?", "suspension_change": 1},
        )
        assert response == {"detail": "Choose the card whose suspension changes"}

        # Yellow cards: every second one suspends
        response = await send_tournament_request(
            HTTPMethod.PUT,
            "discipline_settings",
            auth_context,
            json={"suspension_matches_per_red": 1, "yellow_cards_for_suspension": 2},
        )
        assert response == SUCCESS_RESPONSE
        for match in (first, second):
            yellow = {"team_id": brann, "player_name": "Per", "card_type": "YELLOW"}
            await send_tournament_request(
                HTTPMethod.POST, f"matches/{match['id']}/cards", auth_context, json=yellow
            )
        overview = (await send_tournament_request(HTTPMethod.GET, "discipline", auth_context))[
            "data"
        ]
        assert [(s["player_name"], s["reason"]) for s in overview["suspensions"]] == [
            ("Per", "YELLOW_CARDS")
        ]

        # A team that doesn't play in the match
        not_in_match = [
            team_id
            for name, team_id in teams.items()
            if name != "Brann"
            and first["id"] not in [m["id"] for m in await matches_of_team(auth_context, team_id)]
        ][0]
        response = await send_tournament_request(
            HTTPMethod.POST,
            f"matches/{first['id']}/cards",
            auth_context,
            json=red_card(not_in_match),
        )
        assert response == {"detail": "This team doesn't play in this match"}
    finally:
        await clean_up(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_no_cards_in_childrens_football(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    try:
        teams = await set_up_playable_cup(auth_context)  # G10
        brann = teams["Brann"]
        [first, *_] = await matches_of_team(auth_context, brann)
        response = await send_tournament_request(
            HTTPMethod.POST, f"matches/{first['id']}/cards", auth_context, json=red_card(brann)
        )
        assert response == {
            "detail": "Cards are only kept for classes from 13 years with public results"
        }
    finally:
        await clean_up(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_cards_at_the_pitch(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    try:
        teams = await set_up_playable_cup(auth_context, J16)
        brann = teams["Brann"]
        first, second = await matches_of_team(auth_context, brann)
        created = await send_tournament_request(
            HTTPMethod.POST,
            "score_links",
            auth_context,
            json={"name": "Hele cupen", "court_id": None, "valid_hours": 24},
        )
        token = created["data"]["token"]

        response = await send_request(
            HTTPMethod.POST, f"score/{token}/matches/{first['id']}/cards", json=red_card(brann)
        )
        card_id = response["data"]["id"]
        view = (await send_request(HTTPMethod.GET, f"score/{token}"))["data"]
        by_id = {match["id"]: match for match in view["matches"]}
        assert by_id[first["id"]]["discipline_allowed"] is True
        assert [c["id"] for c in by_id[first["id"]]["cards"]] == [card_id]
        assert by_id[second["id"]]["suspended_players"] == [
            {"team_id": brann, "player_name": "Ola Nordmann"}
        ]

        response = await send_request(HTTPMethod.DELETE, f"score/{token}/cards/{card_id}")
        assert response == SUCCESS_RESPONSE
        response = await send_request(HTTPMethod.DELETE, f"score/{token}/cards/{card_id}")
        assert response == {"detail": "This card can't be changed with this link"}
    finally:
        await clean_up(auth_context)
