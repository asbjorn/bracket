import pytest

from bracket.database import database
from bracket.models.db.stage_item_inputs import StageItemInputInsertable
from bracket.schema import rounds, stage_items, stages
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.dummy_records import (
    DUMMY_MOCK_TIME,
    DUMMY_ROUND1,
    DUMMY_STAGE1,
    DUMMY_STAGE2,
    DUMMY_STAGE_ITEM1,
    DUMMY_TEAM1,
)
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    send_request,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import (
    assert_row_count_and_clear,
    inserted_round,
    inserted_stage,
    inserted_stage_item,
    inserted_stage_item_input,
    inserted_team,
)


@pytest.mark.parametrize(("with_auth",), [(True,), (False,)])
@pytest.mark.asyncio(loop_scope="session")
async def test_stages_endpoint(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext, with_auth: bool
) -> None:
    async with (
        inserted_team(DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})),
        inserted_stage(
            DUMMY_STAGE1.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as stage_inserted,
        inserted_stage_item(
            DUMMY_STAGE_ITEM1.model_copy(
                update={"stage_id": stage_inserted.id, "ranking_id": auth_context.ranking.id}
            )
        ) as stage_item_inserted,
        inserted_round(
            DUMMY_ROUND1.model_copy(update={"stage_item_id": stage_item_inserted.id})
        ) as round_inserted,
    ):
        if with_auth:
            response = await send_tournament_request(HTTPMethod.GET, "stages", auth_context, {})
        else:
            response = await send_request(
                HTTPMethod.GET,
                f"tournaments/{auth_context.tournament.id}/stages?no_draft_rounds=true",
            )
        assert response == {
            "data": [
                {
                    "id": stage_inserted.id,
                    "tournament_id": auth_context.tournament.id,
                    "created": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
                    "is_active": True,
                    "category_id": None,
                    "name": "Group Stage",
                    "stage_items": [
                        {
                            "id": stage_item_inserted.id,
                            "stage_id": stage_inserted.id,
                            "ranking_id": auth_context.ranking.id,
                            "name": "Group A",
                            "created": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
                            "type": "ROUND_ROBIN",
                            "team_count": 4,
                            "rounds": [
                                {
                                    "id": round_inserted.id,
                                    "stage_item_id": stage_item_inserted.id,
                                    "created": DUMMY_MOCK_TIME.isoformat().replace("+00:00", "Z"),
                                    "is_draft": False,
                                    "name": "Round 1",
                                    "matches": [],
                                }
                            ],
                            "inputs": [],
                            "type_name": "Round robin",
                        }
                    ],
                }
            ]
        }


@pytest.mark.asyncio(loop_scope="session")
async def test_create_stage(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with inserted_team(
        DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})
    ):
        assert (
            await send_tournament_request(
                HTTPMethod.POST,
                "stages",
                auth_context,
            )
            == SUCCESS_RESPONSE
        )
        await assert_row_count_and_clear(rounds, 1)
        await assert_row_count_and_clear(stage_items, 1)
        await assert_row_count_and_clear(stages, 1)


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_stage(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with (
        inserted_team(DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})),
        inserted_stage(
            DUMMY_STAGE2.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as stage_inserted,
    ):
        assert (
            await send_tournament_request(
                HTTPMethod.DELETE, f"stages/{stage_inserted.id}", auth_context, {}
            )
            == SUCCESS_RESPONSE
        )
        await assert_row_count_and_clear(stages, 0)


@pytest.mark.asyncio(loop_scope="session")
async def test_update_stage(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    body = {"name": "Optimus"}
    async with (
        inserted_team(DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})),
        inserted_stage(
            DUMMY_STAGE1.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as stage_inserted,
        inserted_stage_item(
            DUMMY_STAGE_ITEM1.model_copy(
                update={"stage_id": stage_inserted.id, "ranking_id": auth_context.ranking.id}
            )
        ),
    ):
        assert (
            await send_tournament_request(
                HTTPMethod.PUT, f"stages/{stage_inserted.id}", auth_context, None, body
            )
            == SUCCESS_RESPONSE
        )
        [updated_stage] = await get_full_tournament_details(auth_context.tournament.id)
        assert len(updated_stage.stage_items) == 1
        assert updated_stage.name == body["name"]

        await assert_row_count_and_clear(stage_items, 1)
        await assert_row_count_and_clear(stages, 1)


@pytest.mark.asyncio(loop_scope="session")
async def test_activate_stage(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with (
        inserted_team(DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})),
        inserted_stage(
            DUMMY_STAGE1.model_copy(update={"tournament_id": auth_context.tournament.id})
        ),
        inserted_stage(
            DUMMY_STAGE2.model_copy(update={"tournament_id": auth_context.tournament.id})
        ),
    ):
        assert (
            await send_tournament_request(
                HTTPMethod.POST, "stages/activate?direction=next", auth_context, json={}
            )
            == SUCCESS_RESPONSE
        )

        await assert_row_count_and_clear(stage_items, 1)
        await assert_row_count_and_clear(stages, 1)


@pytest.mark.asyncio(loop_scope="session")
async def test_get_next_stage_rankings(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with (
        inserted_team(DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})),
        inserted_stage(
            DUMMY_STAGE1.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as stage_inserted,
        inserted_stage_item(
            DUMMY_STAGE_ITEM1.model_copy(
                update={"stage_id": stage_inserted.id, "ranking_id": auth_context.ranking.id}
            )
        ),
    ):
        response = await send_tournament_request(
            HTTPMethod.GET, "next_stage_rankings", auth_context
        )

    assert response == {"data": {}}


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_stage_used_for_best_placed_teams(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """A clear 400 instead of a server error when a later stage still refers to the stage."""
    tournament_id = auth_context.tournament.id
    async with (
        inserted_stage(DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id})) as first,
        inserted_stage(DUMMY_STAGE2.model_copy(update={"tournament_id": tournament_id})) as later,
        inserted_stage_item(
            DUMMY_STAGE_ITEM1.model_copy(
                update={"stage_id": later.id, "ranking_id": auth_context.ranking.id}
            )
        ) as playoff,
        inserted_stage_item_input(
            StageItemInputInsertable(
                slot=0, team_id=None, tournament_id=tournament_id, stage_item_id=playoff.id
            )
        ) as best_input,
    ):
        await database.execute(
            "UPDATE stage_item_inputs SET best_from_stage_id = :stage_id, winner_position = 2, "
            "best_rank = 1 WHERE id = :id",
            values={"stage_id": first.id, "id": best_input.id},
        )
        response = await send_tournament_request(
            HTTPMethod.DELETE, f"stages/{first.id}", auth_context
        )
        assert response == {
            "detail": "A later stage takes its best placed teams from this stage, "
            "delete that one first"
        }
        await database.execute(
            "UPDATE stage_item_inputs SET best_from_stage_id = NULL, best_rank = NULL, "
            "winner_position = NULL WHERE id = :id",
            values={"id": best_input.id},
        )
