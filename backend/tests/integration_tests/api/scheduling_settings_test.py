import pytest

from bracket.database import database
from bracket.models.db.category import CategoryInsertable
from bracket.schema import courts, time_windows
from bracket.sql.shared import sql_delete_stage_item_with_foreign_keys
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.dummy_records import DUMMY_MOCK_TIME, DUMMY_STAGE1
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
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
