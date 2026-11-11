import pytest
from heliclockter import datetime_utc, timedelta

from bracket.database import database
from bracket.schema import categories, tournaments
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.http import HTTPMethod
from bracket.utils.types import assert_some
from tests.integration_tests.api.cup_setup_test import delete_cup
from tests.integration_tests.api.score_links_test import delete_score_links, set_up_playable_cup
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    send_request,
    send_request_with_status,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext


async def set_dashboard_public(tournament_id: int, public: bool) -> None:
    await database.execute(
        tournaments.update().where(tournaments.c.id == tournament_id),
        values={"dashboard_public": public},
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_team_calendar_hides_results_of_hidden_classes(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    try:
        team_ids = await set_up_playable_cup(auth_context)
        link = await send_tournament_request(
            HTTPMethod.POST, "score_links", auth_context, json={"name": "Alle"}
        )
        token = link["data"]["token"]
        view = (await send_request(HTTPMethod.GET, f"score/{token}"))["data"]
        brann_match = next(
            m for m in view["matches"] if "Brann" in (m["team1_name"], m["team2_name"])
        )
        result = {"score1": 7, "score2": 5}
        assert (
            await send_request(
                HTTPMethod.PUT, f"score/{token}/matches/{brann_match['id']}", json=result
            )
            == SUCCESS_RESPONSE
        )

        url = f"tournaments/{tournament_id}/teams/{team_ids['Brann']}/calendar.ics"
        calendar, status, headers = await send_request_with_status(HTTPMethod.GET, url)
        assert status == 200
        assert headers["Content-Type"].startswith("text/calendar")
        assert calendar.startswith("BEGIN:VCALENDAR\r\n")
        assert calendar.count("BEGIN:VEVENT") == 2  # Groups of three: two matches
        assert "LOCATION:Bane " in calendar
        # G10 is children's football: the result is hidden
        assert "7–5" not in calendar and "5–7" not in calendar

        [stage] = await get_full_tournament_details(tournament_id)
        await database.execute(
            categories.update().where(categories.c.id == assert_some(stage.category_id)),
            values={"results_public": True},
        )
        calendar, _, _ = await send_request_with_status(HTTPMethod.GET, url)
        assert "7–5" in calendar

        # Only for public dashboards
        await set_dashboard_public(tournament_id, False)
        _, status, _ = await send_request_with_status(HTTPMethod.GET, url)
        assert status == 401
    finally:
        await set_dashboard_public(tournament_id, True)
        await delete_score_links(auth_context)
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_announcement_rules_and_public_delays(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    public = f"tournaments/{tournament_id}/public_notices"
    try:
        assert (await send_request(HTTPMethod.GET, public))["data"] == {
            "announcement": None,
            "delays": [],
        }
        announcement = {"text": " Lyn: kampene står stille ", "level": "WARNING", "until": None}
        response = await send_tournament_request(
            HTTPMethod.PUT, "announcement", auth_context, json={"announcement": announcement}
        )
        assert response == SUCCESS_RESPONSE
        notices = (await send_request(HTTPMethod.GET, public))["data"]
        assert notices["announcement"] == announcement | {"text": "Lyn: kampene står stille"}

        # Expired announcements are not shown publicly, but the organiser still sees them
        expired = announcement | {"until": (datetime_utc.now() - timedelta(minutes=1)).isoformat()}
        await send_tournament_request(
            HTTPMethod.PUT, "announcement", auth_context, json={"announcement": expired}
        )
        assert (await send_request(HTTPMethod.GET, public))["data"]["announcement"] is None
        own = await send_tournament_request(HTTPMethod.GET, "announcement", auth_context)
        assert own["data"]["level"] == "WARNING"

        # Delays from a pitch: only court and minutes, never the message
        await set_up_playable_cup(auth_context)
        link = await send_tournament_request(
            HTTPMethod.POST, "score_links", auth_context, json={"name": "Alle"}
        )
        token = link["data"]["token"]
        notice = {"delay_minutes": 10, "message": "Dommeren er syk"}
        await send_request(HTTPMethod.POST, f"score/{token}/notices", json=notice)
        delays = (await send_request(HTTPMethod.GET, public))["data"]["delays"]
        assert [(d["court_name"], d["delay_minutes"]) for d in delays] == [(None, 10)]
        assert "Dommeren" not in str(delays)

        rules = {"text": "Kampene er 2 x 10 minutter.\nIngen tabeller for 12 år og yngre."}
        response = await send_tournament_request(HTTPMethod.PUT, "rules", auth_context, json=rules)
        assert response == SUCCESS_RESPONSE
        assert (await send_request(HTTPMethod.GET, f"tournaments/{tournament_id}/rules"))[
            "data"
        ] == rules

        # Not public: no notices or rules without logging in
        await set_dashboard_public(tournament_id, False)
        hidden = await send_request(HTTPMethod.GET, public)
        assert "data" not in hidden
    finally:
        await set_dashboard_public(tournament_id, True)
        await send_tournament_request(
            HTTPMethod.PUT, "announcement", auth_context, json={"announcement": None}
        )
        await send_tournament_request(HTTPMethod.PUT, "rules", auth_context, json={"text": ""})
        await delete_score_links(auth_context)
        await delete_cup(auth_context)
