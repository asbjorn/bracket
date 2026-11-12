import pytest

from bracket.database import database
from bracket.sql.courts import get_all_courts_in_tournament
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.http import HTTPMethod
from bracket.utils.id_types import CourtId
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

        # A split pitch can't be split a second time (its parts can, see below)
        split = await send_tournament_request(
            HTTPMethod.POST, f"courts/{full.id}/split", auth_context, json={"parts": 2}
        )
        assert split["detail"] == "This pitch is already split"

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

        await check_nested_split_and_undo(auth_context, full.id, half_a.id)
    finally:
        await delete_cup(auth_context)


async def check_nested_split_and_undo(
    auth_context: AuthContext, full_id: CourtId, half_a_id: CourtId
) -> None:
    """The matches are planned on the halves: split a half again, then undo the whole split."""
    tournament_id = auth_context.tournament.id
    split = await send_tournament_request(
        HTTPMethod.POST,
        f"courts/{half_a_id}/split",
        auth_context,
        json={"parts": 2, "game_format": "5v5"},
    )
    names = {c["name"]: c for c in split["data"]}
    assert names["Bane 1A1"]["parent_court_id"] == half_a_id
    assert names["Bane 1A2"]["parent_court_id"] == half_a_id

    on_parts = await send_tournament_request(
        HTTPMethod.GET, f"courts/{full_id}/split", auth_context
    )
    planned = on_parts["data"]
    assert len(planned) > 0
    assert {m["court_name"] for m in planned} <= {"Bane 1A", "Bane 1B"}

    # Planned matches on the parts: only with consent
    refused = await send_tournament_request(
        HTTPMethod.DELETE, f"courts/{full_id}/split", auth_context
    )
    assert refused["detail"] == f"{len(planned)} matches are planned on the parts of this pitch"

    # A played match on a part blocks it
    await database.execute(
        "UPDATE matches SET played = true WHERE id = :id", values={"id": planned[0]["id"]}
    )
    blocked = await send_tournament_request(
        HTTPMethod.DELETE, f"courts/{full_id}/split?unschedule_matches=true", auth_context
    )
    assert blocked["detail"].startswith("1 played or started matches")
    await database.execute(
        "UPDATE matches SET played = false WHERE id = :id", values={"id": planned[0]["id"]}
    )

    undone = await send_tournament_request(
        HTTPMethod.DELETE, f"courts/{full_id}/split?unschedule_matches=true", auth_context
    )
    assert [c["name"] for c in undone["data"]] == ["Bane 1"]
    [stage] = await get_full_tournament_details(tournament_id)
    matches = [m for item in stage.stage_items for r in item.rounds for m in r.matches]
    assert all(m.court_id is None and m.start_time is None for m in matches)

    not_split = await send_tournament_request(
        HTTPMethod.DELETE, f"courts/{full_id}/split", auth_context
    )
    assert not_split["detail"] == "This pitch isn't split"
    missing = await send_tournament_request(HTTPMethod.DELETE, "courts/999999/split", auth_context)
    assert missing["detail"] == "Could not find the court"
