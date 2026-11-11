import pytest

from bracket.database import database
from bracket.schema import teams
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.teams import get_teams_with_members
from bracket.utils.http import HTTPMethod
from bracket.utils.types import JsonDict, assert_some
from tests.integration_tests.api.cup_setup_test import G10, J14, WINDOW, delete_cup
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    send_request_with_status,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext


async def play_all(auth_context: AuthContext, stage_id: int) -> None:
    """Every match of the stage: the team in the lower slot / first input wins 1-0."""
    [stage] = [
        s for s in await get_full_tournament_details(auth_context.tournament.id) if s.id == stage_id
    ]
    for item in stage.stage_items:
        for round_ in sorted(item.rounds, key=lambda r: r.id):
            for match in round_.matches:
                response = await send_tournament_request(
                    HTTPMethod.PUT,
                    f"matches/{match.id}",
                    auth_context,
                    json={
                        "round_id": round_.id,
                        "stage_item_input1_score": 1,
                        "stage_item_input2_score": 0,
                        "played": True,
                    },
                )
                assert response == SUCCESS_RESPONSE


@pytest.mark.asyncio(loop_scope="session")
async def test_final_placings_ceremony_and_medals(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    try:
        body: JsonDict = {"classes": [J14, G10 | {"team_count": 4, "group_size": 4}]}
        body["time_windows"] = [WINDOW]
        body["courts"] = [
            {"count": 2, "name_prefix": "Bane", "game_format": "9v9"},
            {"count": 1, "name_prefix": "Bane", "game_format": "7v7"},
        ]
        assert (
            await send_tournament_request(HTTPMethod.POST, "cup_setup", auth_context, json=body)
            == SUCCESS_RESPONSE
        )
        stages = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        j14_groups, j14_playoffs, g10_groups = stages
        for category_id, count, prefix in (
            (j14_groups.category_id, 8, "J"),
            (g10_groups.category_id, 4, "G"),
        ):
            names = "\n".join(f"{prefix}{i}" for i in range(1, count + 1))
            response = await send_tournament_request(
                HTTPMethod.POST,
                "teams_multi",
                auth_context,
                json={"names": names, "active": True, "category_id": category_id},
            )
            assert response == SUCCESS_RESPONSE
        for stage in (j14_groups, g10_groups):
            class_teams = await get_teams_with_members(
                tournament_id, category_id=assert_some(stage.category_id)
            )
            response = await send_tournament_request(
                HTTPMethod.POST,
                f"stages/{stage.id}/draw",
                auth_context,
                json={"pots": [[t.id for t in class_teams]], "seed": 3},
            )
            assert "data" in response
        await database.execute(
            teams.update().where(teams.c.tournament_id == tournament_id), values={"squad_size": 10}
        )
        assert (await send_tournament_request(HTTPMethod.POST, "schedule/apply", auth_context))[
            "data"
        ]["unscheduled_match_ids"] == []

        # Before the playoffs: no placings yet
        results = (await send_tournament_request(HTTPMethod.GET, "final_results", auth_context))[
            "data"
        ]
        by_name = {result["name"]: result for result in results}
        assert not by_name["J14"]["complete"]

        await play_all(auth_context, j14_groups.id)
        response = await send_tournament_request(
            HTTPMethod.POST,
            "stages/activate",
            auth_context,
            json={"direction": "next", "category_id": j14_groups.category_id},
        )
        assert response == SUCCESS_RESPONSE
        await play_all(auth_context, j14_playoffs.id)
        await play_all(auth_context, g10_groups.id)

        results = (await send_tournament_request(HTTPMethod.GET, "final_results", auth_context))[
            "data"
        ]
        j14, g10 = (next(r for r in results if r["name"] == name) for name in ("J14", "G10"))
        assert j14["complete"]
        a_playoff, b_playoff = j14["podiums"]
        assert a_playoff["knockout"] and a_playoff["complete"]
        # A playoff with a bronze final: four places, each once
        assert [p["place"] for p in a_playoff["placings"]] == [1, 2, 3, 4]
        assert [p["place"] for p in b_playoff["placings"]] == [1, 2, 3, 4]
        assert j14["medal_count"] == 80 and j14["teams_without_squad_size"] == 0
        assert j14["ceremony_time"] is not None
        # Children's class: no placings, all eight teams' players get medals
        assert g10["results_public"] is False and g10["podiums"] == []
        assert len(g10["teams"]) == 4 and g10["medal_count"] == 40

        _, status, _ = await send_request_with_status(
            HTTPMethod.GET, f"tournaments/{tournament_id}/final_results.csv"
        )
        assert status == 401  # Organisers only

        response = await send_tournament_request(
            HTTPMethod.PUT, "ceremony_settings", auth_context, json={"ceremony_offset_minutes": 30}
        )
        assert response == SUCCESS_RESPONSE
        later = next(
            r
            for r in (await send_tournament_request(HTTPMethod.GET, "final_results", auth_context))[
                "data"
            ]
            if r["name"] == "J14"
        )
        assert later["ceremony_time"] > j14["ceremony_time"]
    finally:
        await database.execute(
            "UPDATE tournaments SET ceremony_offset_minutes = 15 WHERE id = :id",
            values={"id": tournament_id},
        )
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_drawing_lots(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    try:
        body: JsonDict = {"classes": [J14], "time_windows": [WINDOW]}
        await send_tournament_request(HTTPMethod.POST, "cup_setup", auth_context, json=body)
        group_a, group_b = sorted(
            (await get_full_tournament_details(tournament_id))[0].stage_items, key=lambda i: i.name
        )
        lots = [
            {"stage_item_input_id": input_.id, "lot_number": index}
            for index, input_ in enumerate(group_a.inputs, start=1)
        ]
        response = await send_tournament_request(
            HTTPMethod.PUT, f"stage_items/{group_a.id}/lots", auth_context, json={"lots": lots}
        )
        assert response == SUCCESS_RESPONSE
        [updated] = [
            item
            for stage in await get_full_tournament_details(tournament_id)
            for item in stage.stage_items
            if item.id == group_a.id
        ]
        assert sorted(i.lot_number for i in updated.inputs if i.lot_number) == [1, 2, 3, 4]

        # A place of another group can't be drawn here
        response = await send_tournament_request(
            HTTPMethod.PUT,
            f"stage_items/{group_a.id}/lots",
            auth_context,
            json={"lots": [{"stage_item_input_id": group_b.inputs[0].id, "lot_number": 1}]},
        )
        assert response == {"detail": "Some of the places don't belong to this group"}
    finally:
        await delete_cup(auth_context)
