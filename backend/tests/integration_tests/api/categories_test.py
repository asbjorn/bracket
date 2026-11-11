import pytest

from bracket.database import database
from bracket.models.db.category import CategoryInsertable
from bracket.models.db.stage_item_inputs import StageItemInputInsertable
from bracket.schema import categories, stages, teams
from bracket.utils.dummy_records import (
    DUMMY_MOCK_TIME,
    DUMMY_STAGE1,
    DUMMY_STAGE2,
    DUMMY_STAGE_ITEM1,
    DUMMY_TEAM1,
    DUMMY_TEAM2,
)
from bracket.utils.http import HTTPMethod
from bracket.utils.id_types import TournamentId
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import (
    assert_row_count_and_clear,
    inserted_category,
    inserted_stage,
    inserted_stage_item,
    inserted_stage_item_input,
    inserted_team,
)


def category_g10(tournament_id: TournamentId) -> CategoryInsertable:
    return CategoryInsertable(
        tournament_id=tournament_id,
        name="G10",
        created=DUMMY_MOCK_TIME,
        age=10,
        results_public=False,
    )


def category_j14(tournament_id: TournamentId) -> CategoryInsertable:
    return CategoryInsertable(
        tournament_id=tournament_id,
        name="J14",
        created=DUMMY_MOCK_TIME,
        age=14,
        results_public=True,
    )


@pytest.mark.parametrize(
    ("body", "expected_results_public"),
    [
        pytest.param({"name": "G10", "age": 10}, False, id="children: results hidden by default"),
        pytest.param({"name": "G12", "age": 12}, False, id="12 is still children's football"),
        pytest.param({"name": "J13", "age": 13}, True, id="youth: results public by default"),
        pytest.param({"name": "Open"}, True, id="no age: results public by default"),
        pytest.param(
            {"name": "G10", "age": 10, "results_public": True}, True, id="explicit override"
        ),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_create_category(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
    body: dict[str, str | int | bool],
    expected_results_public: bool,
) -> None:
    response = await send_tournament_request(HTTPMethod.POST, "categories", auth_context, json=body)
    await assert_row_count_and_clear(categories, 1)

    assert response["data"]["name"] == body["name"]
    assert response["data"]["age"] == body.get("age")
    assert response["data"]["results_public"] is expected_results_public
    assert response["data"]["tournament_id"] == auth_context.tournament.id


@pytest.mark.asyncio(loop_scope="session")
async def test_get_categories_sorted_by_age(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    async with (
        inserted_category(category_j14(tournament_id)) as j14,
        inserted_category(category_g10(tournament_id)) as g10,
    ):
        response = await send_tournament_request(HTTPMethod.GET, "categories", auth_context)

    assert [category["id"] for category in response["data"]] == [g10.id, j14.id]


@pytest.mark.asyncio(loop_scope="session")
async def test_category_name_must_be_unique(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with inserted_category(category_g10(auth_context.tournament.id)):
        response = await send_tournament_request(
            HTTPMethod.POST, "categories", auth_context, json={"name": "G10"}
        )

    assert response == {"detail": "A class with this name already exists"}


@pytest.mark.asyncio(loop_scope="session")
async def test_update_category(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with inserted_category(category_g10(auth_context.tournament.id)) as category:
        response = await send_tournament_request(
            HTTPMethod.PUT,
            f"categories/{category.id}",
            auth_context,
            json={"name": "G11", "age": 11, "results_public": True},
        )

    assert response["data"] | {"created": None} == {
        "id": category.id,
        "tournament_id": auth_context.tournament.id,
        "name": "G11",
        "age": 11,
        "results_public": True,
        "created": None,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_update_unknown_category(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    response = await send_tournament_request(
        HTTPMethod.PUT, "categories/-42", auth_context, json={"name": "G11"}
    )
    assert response == {"detail": "Could not find class with id -42"}


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_category(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with inserted_category(category_g10(auth_context.tournament.id)) as category:
        response = await send_tournament_request(
            HTTPMethod.DELETE, f"categories/{category.id}", auth_context
        )
        assert response == SUCCESS_RESPONSE
        assert await database.fetch_all(categories.select()) == []


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_category_in_use(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    async with (
        inserted_category(category_g10(tournament_id)) as category,
        inserted_team(
            DUMMY_TEAM1.model_copy(
                update={"tournament_id": tournament_id, "category_id": category.id}
            )
        ),
    ):
        response = await send_tournament_request(
            HTTPMethod.DELETE, f"categories/{category.id}", auth_context
        )

    assert response == {
        "detail": "This class still has teams, move them to another class or delete them first"
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_create_team_with_category_and_filter(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    async with (
        inserted_category(category_g10(tournament_id)) as g10,
        inserted_team(DUMMY_TEAM2.model_copy(update={"tournament_id": tournament_id})),
    ):
        response = await send_tournament_request(
            HTTPMethod.POST,
            "teams",
            auth_context,
            json={"name": "Team G10", "active": True, "player_ids": [], "category_id": g10.id},
        )
        assert response["data"]["category_id"] == g10.id

        filtered = await send_tournament_request(
            HTTPMethod.GET, f"teams?category_id={g10.id}", auth_context
        )
        assert [team["name"] for team in filtered["data"]["teams"]] == ["Team G10"]
        assert filtered["data"]["count"] == 1

        unfiltered = await send_tournament_request(HTTPMethod.GET, "teams", auth_context)
        assert unfiltered["data"]["count"] == 2

        await database.execute(teams.delete().where(teams.c.id == response["data"]["id"]))


@pytest.mark.asyncio(loop_scope="session")
async def test_create_team_with_unknown_category(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    response = await send_tournament_request(
        HTTPMethod.POST,
        "teams",
        auth_context,
        json={"name": "Team", "active": True, "player_ids": [], "category_id": -42},
    )
    assert response == {"detail": "Could not find Category(s) with ID -42"}


@pytest.mark.asyncio(loop_scope="session")
async def test_create_stage_with_category(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with inserted_category(category_g10(auth_context.tournament.id)) as g10:
        response = await send_tournament_request(
            HTTPMethod.POST, "stages", auth_context, json={"category_id": g10.id}
        )
        assert response == SUCCESS_RESPONSE

        [stage] = await database.fetch_all(stages.select())
        assert stage["category_id"] == g10.id
        await assert_row_count_and_clear(stages, 1)


@pytest.mark.asyncio(loop_scope="session")
async def test_activate_next_stage_per_category(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """
    Activating the next stage of one age class must not change the active stage of another class.
    """
    tournament_id = auth_context.tournament.id
    async with (
        inserted_category(category_g10(tournament_id)) as g10,
        inserted_category(category_j14(tournament_id)) as j14,
        inserted_stage(
            DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id, "category_id": g10.id})
        ) as g10_stage1,
        inserted_stage(
            DUMMY_STAGE2.model_copy(update={"tournament_id": tournament_id, "category_id": g10.id})
        ) as g10_stage2,
        inserted_stage(
            DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id, "category_id": j14.id})
        ) as j14_stage1,
        inserted_stage(
            DUMMY_STAGE2.model_copy(update={"tournament_id": tournament_id, "category_id": j14.id})
        ) as j14_stage2,
    ):
        response = await send_tournament_request(
            HTTPMethod.POST,
            "stages/activate",
            auth_context,
            json={"direction": "next", "category_id": g10.id},
        )
        assert response == SUCCESS_RESPONSE

        active = {row["id"]: row["is_active"] for row in await database.fetch_all(stages.select())}
        assert active == {
            g10_stage1.id: False,
            g10_stage2.id: True,
            j14_stage1.id: True,
            j14_stage2.id: False,
        }

        # There is no next stage for G10 anymore, but J14 still has one.
        response = await send_tournament_request(
            HTTPMethod.POST,
            "stages/activate",
            auth_context,
            json={"direction": "next", "category_id": g10.id},
        )
        assert response == {"detail": "There is no next stage"}


@pytest.mark.asyncio(loop_scope="session")
async def test_team_of_other_category_cannot_be_input(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    async with (
        inserted_category(category_g10(tournament_id)) as g10,
        inserted_category(category_j14(tournament_id)) as j14,
        inserted_team(
            DUMMY_TEAM1.model_copy(update={"tournament_id": tournament_id, "category_id": j14.id})
        ) as j14_team,
        inserted_stage(
            DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id, "category_id": g10.id})
        ) as g10_stage,
        inserted_stage_item(
            DUMMY_STAGE_ITEM1.model_copy(
                update={"stage_id": g10_stage.id, "ranking_id": auth_context.ranking.id}
            )
        ) as stage_item,
        inserted_stage_item_input(
            StageItemInputInsertable(
                slot=0, team_id=None, tournament_id=tournament_id, stage_item_id=stage_item.id
            )
        ) as stage_item_input,
    ):
        response = await send_tournament_request(
            HTTPMethod.PUT,
            f"stage_items/{stage_item.id}/inputs/{stage_item_input.id}",
            auth_context,
            json={"team_id": j14_team.id},
        )
        assert response == {"detail": "This team belongs to another class than this stage"}

        available = await send_tournament_request(HTTPMethod.GET, "available_inputs", auth_context)
        assert available == {"data": {str(g10_stage.id): []}}


@pytest.mark.asyncio(loop_scope="session")
async def test_placed_team_cannot_change_category(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    async with (
        inserted_category(category_g10(tournament_id)) as g10,
        inserted_category(category_j14(tournament_id)) as j14,
        inserted_team(
            DUMMY_TEAM1.model_copy(update={"tournament_id": tournament_id, "category_id": g10.id})
        ) as team,
        inserted_stage(
            DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id, "category_id": g10.id})
        ) as g10_stage,
        inserted_stage_item(
            DUMMY_STAGE_ITEM1.model_copy(
                update={"stage_id": g10_stage.id, "ranking_id": auth_context.ranking.id}
            )
        ) as stage_item,
        inserted_stage_item_input(
            StageItemInputInsertable(
                slot=0, team_id=team.id, tournament_id=tournament_id, stage_item_id=stage_item.id
            )
        ),
    ):
        response = await send_tournament_request(
            HTTPMethod.PUT,
            f"teams/{team.id}",
            auth_context,
            json={"name": team.name, "active": True, "player_ids": [], "category_id": j14.id},
        )
        assert response == {
            "detail": "Team is placed in a stage of its class, remove it there first"
        }

        # Changing other fields while keeping the class is fine
        response = await send_tournament_request(
            HTTPMethod.PUT,
            f"teams/{team.id}",
            auth_context,
            json={"name": "Renamed", "active": True, "player_ids": [], "category_id": g10.id},
        )
        assert response["data"]["name"] == "Renamed"


@pytest.mark.asyncio(loop_scope="session")
async def test_winner_of_other_category_cannot_be_input(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    async with (
        inserted_category(category_g10(tournament_id)) as g10,
        inserted_category(category_j14(tournament_id)) as j14,
        inserted_stage(
            DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id, "category_id": g10.id})
        ) as g10_group_stage,
        inserted_stage_item(
            DUMMY_STAGE_ITEM1.model_copy(
                update={"stage_id": g10_group_stage.id, "ranking_id": auth_context.ranking.id}
            )
        ) as g10_group,
        inserted_stage(
            DUMMY_STAGE2.model_copy(update={"tournament_id": tournament_id, "category_id": j14.id})
        ) as j14_playoff_stage,
        inserted_stage_item(
            DUMMY_STAGE_ITEM1.model_copy(
                update={"stage_id": j14_playoff_stage.id, "ranking_id": auth_context.ranking.id}
            )
        ) as j14_playoff,
        inserted_stage_item_input(
            StageItemInputInsertable(
                slot=0, team_id=None, tournament_id=tournament_id, stage_item_id=j14_playoff.id
            )
        ) as stage_item_input,
    ):
        response = await send_tournament_request(
            HTTPMethod.PUT,
            f"stage_items/{j14_playoff.id}/inputs/{stage_item_input.id}",
            auth_context,
            json={"winner_from_stage_item_id": g10_group.id, "winner_position": 1},
        )
        assert response == {"detail": "Teams can only advance to stages of the same class"}

        available = await send_tournament_request(HTTPMethod.GET, "available_inputs", auth_context)
        assert available["data"][str(j14_playoff_stage.id)] == []


@pytest.mark.asyncio(loop_scope="session")
async def test_category_warnings_endpoint(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    async with (
        inserted_category(category_g10(tournament_id)) as g10,
        inserted_team(
            DUMMY_TEAM1.model_copy(update={"tournament_id": tournament_id, "category_id": g10.id})
        ),
    ):
        response = await send_tournament_request(HTTPMethod.GET, "category_warnings", auth_context)

    assert response == {
        "data": {
            str(g10.id): [
                {"code": "UNPLACED_TEAMS", "minimum_matches": None, "team_names": ["Team 1"]}
            ]
        }
    }
