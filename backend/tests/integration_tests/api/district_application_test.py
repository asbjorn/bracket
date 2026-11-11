import pytest

from bracket.database import database
from bracket.logic.district_application import playing_days
from bracket.models.db.time_window import TimeWindow
from bracket.schema import tournament_details
from bracket.utils.http import HTTPMethod
from bracket.utils.id_types import TimeWindowId, TournamentId
from tests.integration_tests.api.cup_setup_test import delete_cup
from tests.integration_tests.api.score_links_test import set_up_playable_cup
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    send_request,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext


def window(start: str, end: str) -> TimeWindow:
    return TimeWindow.model_validate(
        {
            "id": TimeWindowId(1),
            "tournament_id": TournamentId(1),
            "start_time": start,
            "end_time": end,
        }
    )


def test_playing_days_in_norwegian_time() -> None:
    days = playing_days(
        [
            window("2026-06-14T10:45:00Z", "2026-06-14T15:00:00Z"),
            window("2026-06-13T07:00:00Z", "2026-06-13T10:00:00Z"),
            window("2026-06-14T07:00:00Z", "2026-06-14T10:00:00Z"),
            # 23:30 UTC on the 13th is already the 14th in Norway
            window("2026-06-13T22:30:00Z", "2026-06-13T23:00:00Z"),
        ]
    )
    assert [(str(d.day), d.first_start, d.last_end, d.windows) for d in days] == [
        ("2026-06-13", "09:00", "12:00", ["09:00-12:00"]),
        ("2026-06-14", "00:30", "17:00", ["00:30-01:00", "09:00-12:00", "12:45-17:00"]),
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_district_application(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    try:
        await set_up_playable_cup(auth_context)
        details = {
            "organiser_club": "Brann",
            "contact_name": "Kari Nordmann",
            "contact_phone": "+47 900 00 000",
            "contact_email": "kari@example.org",
            "jury_chair_name": "Per Hansen",
            "jury_chair_phone": "+47 911 11 111",
            "venue": "Brann stadion",
            "rules_summary": "NFFs regler for barnefotball",
            "notes": "",
        }
        response = await send_tournament_request(
            HTTPMethod.PUT, "details", auth_context, json=details
        )
        assert response == SUCCESS_RESPONSE

        data = (
            await send_tournament_request(HTTPMethod.GET, "district_application", auth_context)
        )["data"]
        assert data["details"] == details | {"notes": None}
        # The window 07:00-15:00 UTC is 09:00-17:00 in Norwegian summer time
        assert data["days"] == [
            {
                "day": "2026-06-13",
                "first_start": "09:00",
                "last_end": "17:00",
                "windows": ["09:00-17:00"],
            }
        ]
        assert data["courts"] == [{"game_format": "7v7", "count": 2}]
        [g10] = data["classes"]
        assert (g10["name"], g10["age"], g10["team_count"], g10["match_count"]) == (
            "G10",
            10,
            6,
            6,
        )
        assert (g10["results_public"], g10["has_playoffs"], g10["duration_minutes"]) == (
            False,
            False,
            10,
        )
        assert (data["team_count"], data["match_count"]) == (6, 6)

        # Organiser only: the contact details are personal data
        unauthorized = await send_request(
            HTTPMethod.GET, f"tournaments/{tournament_id}/district_application"
        )
        assert unauthorized == {"detail": "Not authenticated"}
    finally:
        await database.execute(
            tournament_details.delete().where(tournament_details.c.tournament_id == tournament_id)
        )
        await delete_cup(auth_context)
