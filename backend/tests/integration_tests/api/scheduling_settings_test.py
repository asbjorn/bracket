import pytest

from bracket.database import database
from bracket.models.db.category import CategoryInsertable
from bracket.models.db.game_format import GameFormat
from bracket.schema import courts, time_windows
from bracket.sql.shared import sql_delete_stage_item_with_foreign_keys
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.dummy_records import DUMMY_MOCK_TIME, DUMMY_STAGE1
from bracket.utils.http import HTTPMethod
from bracket.utils.types import assert_some
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    send_auth_request,
    send_request,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import inserted_category, inserted_stage


@pytest.mark.asyncio(loop_scope="session")
async def test_class_timing_applies_to_its_matches(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """
    Matches of a class with its own duration and margin get those; when the class changes,
    its matches follow.
    """
    tournament_id = auth_context.tournament.id
    async with (
        inserted_category(
            CategoryInsertable(
                tournament_id=tournament_id,
                name="G10",
                created=DUMMY_MOCK_TIME,
                age=10,
                results_public=False,
                duration_minutes=12,
                margin_minutes=3,
            )
        ) as g10,
        inserted_stage(
            DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id, "category_id": g10.id})
        ) as stage,
    ):
        response = await send_tournament_request(
            HTTPMethod.POST,
            "stage_items",
            auth_context,
            json={"stage_id": stage.id, "type": "ROUND_ROBIN", "team_count": 4},
        )
        assert response == SUCCESS_RESPONSE
        [stage_with_items] = await get_full_tournament_details(tournament_id)
        [group] = stage_with_items.stage_items
        try:
            matches = [match for round_ in group.rounds for match in round_.matches]
            assert len(matches) == 6
            assert {(m.duration_minutes, m.margin_minutes) for m in matches} == {(12, 3)}

            response = await send_tournament_request(
                HTTPMethod.PUT,
                f"categories/{g10.id}",
                auth_context,
                json={"name": "G10", "age": 10, "duration_minutes": 8},
            )
            assert response["data"]["duration_minutes"] == 8
            [stage_with_items] = await get_full_tournament_details(tournament_id)
            matches = [m for r in stage_with_items.stage_items[0].rounds for m in r.matches]
            # No class margin anymore: the tournament default (5) applies
            assert {(m.duration_minutes, m.margin_minutes) for m in matches} == {(8, 5)}
        finally:
            await sql_delete_stage_item_with_foreign_keys(group.id)


@pytest.mark.asyncio(loop_scope="session")
async def test_time_windows(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    saturday = [
        {"start_time": "2026-06-13T07:00:00Z", "end_time": "2026-06-13T10:00:00Z"},
        {"start_time": "2026-06-13T10:45:00Z", "end_time": "2026-06-13T15:00:00Z"},
    ]
    response = await send_tournament_request(
        HTTPMethod.PUT, "time_windows", auth_context, json={"time_windows": saturday}
    )
    assert [(w["start_time"], w["end_time"]) for w in response["data"]] == [
        ("2026-06-13T07:00:00Z", "2026-06-13T10:00:00Z"),
        ("2026-06-13T10:45:00Z", "2026-06-13T15:00:00Z"),
    ]

    # Replacing keeps only the new windows
    response = await send_tournament_request(
        HTTPMethod.PUT, "time_windows", auth_context, json={"time_windows": saturday[:1]}
    )
    assert len(response["data"]) == 1
    assert (
        len((await send_tournament_request(HTTPMethod.GET, "time_windows", auth_context))["data"])
        == 1
    )

    overlapping = [
        saturday[0],
        {"start_time": "2026-06-13T09:00:00Z", "end_time": "2026-06-13T11:00:00Z"},
    ]
    response = await send_tournament_request(
        HTTPMethod.PUT, "time_windows", auth_context, json={"time_windows": overlapping}
    )
    assert "Time windows can't overlap" in str(response["detail"])

    backwards = [{"start_time": "2026-06-13T10:00:00Z", "end_time": "2026-06-13T09:00:00Z"}]
    response = await send_tournament_request(
        HTTPMethod.PUT, "time_windows", auth_context, json={"time_windows": backwards}
    )
    assert "must end after it starts" in str(response["detail"])

    await database.execute(time_windows.delete())


@pytest.mark.asyncio(loop_scope="session")
async def test_create_multiple_courts_continues_numbering(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    response = await send_tournament_request(
        HTTPMethod.POST,
        "courts_multi",
        auth_context,
        json={"count": 2, "name_prefix": "Bane", "game_format": "7v7"},
    )
    assert [(c["name"], c["game_format"]) for c in response["data"]] == [
        ("Bane 1", "7v7"),
        ("Bane 2", "7v7"),
    ]
    response = await send_tournament_request(
        HTTPMethod.POST, "courts_multi", auth_context, json={"count": 1, "name_prefix": "Bane"}
    )
    assert [c["name"] for c in response["data"]] == ["Bane 1", "Bane 2", "Bane 3"]
    await database.execute(courts.delete())


@pytest.mark.asyncio(loop_scope="session")
async def test_propose_and_apply_schedule(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """
    G10 plays 5v5 (10 + 2 min), J14 plays 7v7 (15 + 3 min, 10 min rest). Each class has its
    own court. Everything fits in 09:00-12:00; in 09:00-09:30 it doesn't, and the report says
    what's missing.
    """
    tournament_id = auth_context.tournament.id
    async with (
        inserted_category(
            CategoryInsertable(
                tournament_id=tournament_id,
                name="G10",
                created=DUMMY_MOCK_TIME,
                results_public=False,
                duration_minutes=10,
                margin_minutes=2,
                game_format=GameFormat.FIVE_A_SIDE,
            )
        ) as g10,
        inserted_category(
            CategoryInsertable(
                tournament_id=tournament_id,
                name="J14",
                created=DUMMY_MOCK_TIME,
                duration_minutes=15,
                margin_minutes=3,
                min_rest_minutes=10,
                game_format=GameFormat.SEVEN_A_SIDE,
            )
        ) as j14,
        inserted_stage(
            DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id, "category_id": g10.id})
        ) as g10_stage,
        inserted_stage(
            DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id, "category_id": j14.id})
        ) as j14_stage,
    ):
        for stage_id in (g10_stage.id, j14_stage.id):
            response = await send_tournament_request(
                HTTPMethod.POST,
                "stage_items",
                auth_context,
                json={"stage_id": stage_id, "type": "ROUND_ROBIN", "team_count": 4},
            )
            assert response == SUCCESS_RESPONSE
        for game_format in ("5v5", "7v7"):
            response = await send_tournament_request(
                HTTPMethod.POST,
                "courts_multi",
                auth_context,
                json={"count": 1, "name_prefix": f"Bane {game_format}", "game_format": game_format},
            )
        court_of_format = {c["game_format"]: c["id"] for c in response["data"]}
        stages = await get_full_tournament_details(tournament_id)
        try:
            await send_tournament_request(
                HTTPMethod.PUT,
                "time_windows",
                auth_context,
                json={
                    "time_windows": [
                        {"start_time": "2026-06-13T09:00:00Z", "end_time": "2026-06-13T12:00:00Z"}
                    ]
                },
            )
            proposal = (
                await send_tournament_request(HTTPMethod.POST, "schedule/propose", auth_context)
            )["data"]
            assert proposal["unscheduled_match_ids"] == []
            assert proposal["extra_courts"] == []
            assert proposal["extra_minutes"] == 0
            assert proposal["matches_total"] == 12

            match_class = {
                m.id: stage.category_id
                for stage in stages
                for item in stage.stage_items
                for r in item.rounds
                for m in r.matches
            }
            planned = {m["match_id"]: m for m in proposal["matches"]}
            for match_id, class_id in match_class.items():
                expected_court = court_of_format["5v5" if class_id == g10.id else "7v7"]
                assert planned[match_id]["court_id"] == expected_court
            # J14 on one court: 15 + 3 min per match plus 10 min rest; teams can't play every
            # slot, so the last match ends later than 6 x 18 minutes after 09:00
            assert proposal["last_end"] > "2026-06-13T10:48:00Z"

            # Applying saves the same plan
            applied = (
                await send_tournament_request(HTTPMethod.POST, "schedule/apply", auth_context)
            )["data"]
            assert applied["matches"] == proposal["matches"]
            saved = {
                m.id: (m.court_id, m.start_time)
                for stage in await get_full_tournament_details(tournament_id)
                for item in stage.stage_items
                for r in item.rounds
                for m in r.matches
            }
            for match in proposal["matches"]:
                court_id, start_time = saved[match["match_id"]]
                assert court_id == match["court_id"]
                assert (
                    assert_some(start_time).isoformat().replace("+00:00", "Z")
                    == match["start_time"]
                )

            # 30 minutes is far too short: the report says how many courts or minutes are missing
            await send_tournament_request(
                HTTPMethod.PUT,
                "time_windows",
                auth_context,
                json={
                    "time_windows": [
                        {"start_time": "2026-06-13T09:00:00Z", "end_time": "2026-06-13T09:30:00Z"}
                    ]
                },
            )
            proposal = (
                await send_tournament_request(HTTPMethod.POST, "schedule/propose", auth_context)
            )["data"]
            assert len(proposal["unscheduled_match_ids"]) > 0
            # A J14 team plays 3 matches of 15 minutes with 10 minutes rest in between: that
            # can't fit in 30 minutes, whatever the number of courts. Only more time helps.
            assert proposal["extra_courts"] is None
            assert proposal["extra_minutes"] > 0
        finally:
            for stage in stages:
                for item in stage.stage_items:
                    await sql_delete_stage_item_with_foreign_keys(item.id)
            await database.execute(courts.delete())
            await database.execute(time_windows.delete())


@pytest.mark.asyncio(loop_scope="session")
async def test_delay_and_plan_issues(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    async with inserted_stage(
        DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id})
    ) as stage:
        response = await send_tournament_request(
            HTTPMethod.POST,
            "stage_items",
            auth_context,
            json={"stage_id": stage.id, "type": "ROUND_ROBIN", "team_count": 4},
        )
        assert response == SUCCESS_RESPONSE
        await send_tournament_request(
            HTTPMethod.POST, "courts_multi", auth_context, json={"count": 2, "name_prefix": "Bane"}
        )
        [stage_with_items] = await get_full_tournament_details(tournament_id)
        [group] = stage_with_items.stage_items
        try:
            await send_tournament_request(
                HTTPMethod.PUT,
                "time_windows",
                auth_context,
                json={
                    "time_windows": [
                        {"start_time": "2026-06-13T09:00:00Z", "end_time": "2026-06-13T12:00:00Z"}
                    ]
                },
            )
            await send_tournament_request(HTTPMethod.POST, "schedule/apply", auth_context)
            issues = await send_tournament_request(HTTPMethod.GET, "schedule/issues", auth_context)
            assert issues == {"data": []}

            # The first match has been played: it stays where it is
            [stage_with_items] = await get_full_tournament_details(tournament_id)
            matches = sorted(
                (m for r in stage_with_items.stage_items[0].rounds for m in r.matches),
                key=lambda m: (assert_some(m.start_time), m.id),
            )
            first = matches[0]
            await database.execute(
                "UPDATE matches SET played = true WHERE id = :id", values={"id": first.id}
            )

            response = await send_tournament_request(
                HTTPMethod.POST,
                "schedule/delay",
                auth_context,
                json={"minutes": 180, "from_time": "2026-06-13T08:00:00Z"},
            )
            assert response == {"data": 5}

            # Now everything except the played match is after the time window
            issues = await send_tournament_request(HTTPMethod.GET, "schedule/issues", auth_context)
            outside = {i["match_id"] for i in issues["data"] if i["kind"] == "OUTSIDE_TIME_WINDOWS"}
            assert outside == {m.id for m in matches[1:]}
        finally:
            await sql_delete_stage_item_with_foreign_keys(group.id)
            await database.execute(courts.delete())
            await database.execute(time_windows.delete())


@pytest.mark.asyncio(loop_scope="session")
async def test_capacity_endpoint(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    body = {
        "classes": [
            {
                "name": "G12",
                "age": 12,
                "team_count": 8,
                "group_size": 4,
                "duration_minutes": 8,
                "margin_minutes": 3,
            }
        ],
        "courts": [{"count": 1}],
        "time_windows": [
            {"start_time": "2026-06-13T14:00:00Z", "end_time": "2026-06-13T15:00:00Z"}
        ],
    }
    response = await send_auth_request(HTTPMethod.POST, "capacity", auth_context, json=body)
    schedule = response["data"]["schedule"]
    # 12 matches of 11 minutes don't fit in an hour on one court
    assert len(schedule["unscheduled_match_ids"]) > 0
    assert schedule["extra_courts"] == [{"game_format": None, "count": 2}]
    assert response["data"]["classes"][0]["group_matches"] == 12

    unauthorized = await send_request(HTTPMethod.POST, "capacity", json=body)
    assert unauthorized == {"detail": "Not authenticated"}
