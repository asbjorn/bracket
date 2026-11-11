import pytest

from bracket.sql.courts import get_all_courts_in_tournament
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.http import HTTPMethod
from bracket.utils.types import JsonDict, assert_some
from tests.integration_tests.api.cup_setup_test import G10, WINDOW, delete_cup
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
from tests.integration_tests.models import AuthContext


def windows(*hours: tuple[int, int]) -> JsonDict:
    return {
        "time_windows": [
            {
                "start_time": f"2026-06-13T{start:02}:00:00Z",
                "end_time": f"2026-06-13T{end:02}:00:00Z",
            }
            for start, end in hours
        ]
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_split_pitch_pitch_hours_and_class_hours(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    body: JsonDict = {
        "classes": [G10],
        "courts": [
            {
                "count": 1,
                "name_prefix": "Bane",
                "game_format": "11v11",
                "split_into": 2,
                "part_format": "7v7",
            }
        ],
        "time_windows": [WINDOW],
    }
    try:
        response = await send_tournament_request(
            HTTPMethod.POST, "cup_setup", auth_context, json=body
        )
        assert response == SUCCESS_RESPONSE
        courts = {c.name: c for c in await get_all_courts_in_tournament(tournament_id)}
        full, half_a, half_b = courts["Bane 1"], courts["Bane 1A"], courts["Bane 1B"]
        assert (half_a.parent_court_id, half_b.parent_court_id) == (full.id, full.id)
        assert (full.game_format, half_a.game_format) == ("11v11", "7v7")

        # A split pitch can't be split again, nor can one of its parts
        for court in (full, half_a):
            split = await send_tournament_request(
                HTTPMethod.POST, f"courts/{court.id}/split", auth_context, json={"parts": 2}
            )
            assert split["detail"] in {
                "This pitch is already split",
                "A part of a pitch can't be split again",
            }

        [stage] = await get_full_tournament_details(tournament_id)
        category_id = assert_some(stage.category_id)
        # G10 plays 10-12; half B is only open from 11
        for endpoint, hours in (
            (f"categories/{category_id}/time_windows", windows((10, 12))),
            (f"courts/{half_b.id}/time_windows", windows((11, 15))),
        ):
            response = await send_tournament_request(
                HTTPMethod.PUT, endpoint, auth_context, json=hours
            )
            assert response == SUCCESS_RESPONSE
        hours = await send_tournament_request(HTTPMethod.GET, "planning_hours", auth_context)
        assert set(hours["data"]["courts"]) == {str(half_b.id)}
        assert set(hours["data"]["categories"]) == {str(category_id)}
        # The windows of the cup are unchanged
        cup = await send_tournament_request(HTTPMethod.GET, "time_windows", auth_context)
        assert len(cup["data"]) == 1

        plan = await send_tournament_request(HTTPMethod.POST, "schedule/apply", auth_context)
        assert plan["data"]["unscheduled_match_ids"] == []
        [stage] = await get_full_tournament_details(tournament_id)
        matches = [m for item in stage.stage_items for r in item.rounds for m in r.matches]
        for match in matches:
            start = assert_some(match.start_time)
            assert 10 <= start.hour < 12, start
            assert match.court_id in {half_a.id, half_b.id}
            if match.court_id == half_b.id:
                assert start.hour >= 11
        issues = await send_tournament_request(HTTPMethod.GET, "schedule/issues", auth_context)
        assert issues["data"] == []

        missing = await send_tournament_request(
            HTTPMethod.PUT, "courts/999999/time_windows", auth_context, json=windows((9, 10))
        )
        assert missing == {"detail": "Could not find the court"}
        # Resetting a class to the cup's hours
        reset = await send_tournament_request(
            HTTPMethod.PUT,
            f"categories/{category_id}/time_windows",
            auth_context,
            json={"time_windows": []},
        )
        assert reset == SUCCESS_RESPONSE
        hours = await send_tournament_request(HTTPMethod.GET, "planning_hours", auth_context)
        assert hours["data"]["categories"] == {}
    finally:
        await delete_cup(auth_context)
