from contextlib import AsyncExitStack

import asyncpg  # type: ignore[import-untyped]
import pytest

from bracket.database import database
from bracket.models.db.category import CategoryInsertable
from bracket.models.db.stage_item_inputs import (
    StageItemInputEmpty,
    StageItemInputFinal,
    StageItemInputTentative,
)
from bracket.models.db.util import StageWithStageItems
from bracket.sql.shared import sql_delete_stage_item_with_foreign_keys
from bracket.sql.stages import get_full_tournament_details, sql_delete_stage
from bracket.utils.dummy_records import DUMMY_MOCK_TIME, DUMMY_STAGE1, DUMMY_TEAM1
from bracket.utils.http import HTTPMethod
from bracket.utils.id_types import StageId
from bracket.utils.types import JsonDict, assert_some
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import inserted_category, inserted_stage, inserted_team


async def delete_stages_except(auth_context: AuthContext, stage_id: StageId) -> None:
    # Later stages first: their inputs refer to the groups of earlier stages
    stages = await get_full_tournament_details(auth_context.tournament.id)
    for stage in sorted(stages, key=lambda stage: stage.id, reverse=True):
        for stage_item in stage.stage_items:
            await sql_delete_stage_item_with_foreign_keys(stage_item.id)
        if stage.id != stage_id:
            await sql_delete_stage(auth_context.tournament.id, stage.id)


async def create_groups(auth_context: AuthContext, stage_id: StageId, letters: str) -> None:
    for letter in letters:
        response = await send_tournament_request(
            HTTPMethod.POST,
            "stage_items",
            auth_context,
            json={
                "stage_id": stage_id,
                "type": "ROUND_ROBIN",
                "team_count": 4,
                "name": f"Group {letter}",
            },
        )
        assert response == SUCCESS_RESPONSE


def first_round_team_names(stage: StageWithStageItems, playoff_name: str) -> list[list[str]]:
    [playoff] = [item for item in stage.stage_items if item.name == playoff_name]
    first_round = min(playoff.rounds, key=lambda r: r.id)
    return [
        [
            input_.team.name
            for input_ in (match.stage_item_input1, match.stage_item_input2)
            if isinstance(input_, StageItemInputFinal)
        ]
        for match in sorted(first_round.matches, key=lambda m: m.id)
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_a_and_b_playoffs_after_two_groups(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """
    Two groups of 4 are played (the team in the lower slot always wins), then an A playoff for
    placings 1-2 and a B playoff for 3-4 is created. After activating it, the semifinals are
    crossed: 1A-2B and 1B-2A.
    """
    tournament_id = auth_context.tournament.id

    async def request(method: HTTPMethod, endpoint: str, json: JsonDict | None = None) -> JsonDict:
        return await send_tournament_request(method, endpoint, auth_context, json=json)

    async with AsyncExitStack() as stack:
        group_stage = await stack.enter_async_context(
            inserted_stage(DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id}))
        )
        teams = [
            await stack.enter_async_context(
                inserted_team(
                    DUMMY_TEAM1.model_copy(
                        update={"tournament_id": tournament_id, "name": f"{letter}{slot}"}
                    )
                )
            )
            for letter in "AB"
            for slot in range(1, 5)
        ]
        try:
            await create_groups(auth_context, group_stage.id, "AB")

            [stage] = await get_full_tournament_details(tournament_id)
            for group in stage.stage_items:
                letter = group.name[-1]
                for input_ in group.inputs:
                    [team] = [t for t in teams if t.name == f"{letter}{input_.slot}"]
                    response = await request(
                        HTTPMethod.PUT,
                        f"stage_items/{group.id}/inputs/{input_.id}",
                        {"team_id": team.id},
                    )
                    assert response == SUCCESS_RESPONSE

            [stage] = await get_full_tournament_details(tournament_id)
            for group in stage.stage_items:
                slot_of_input = {input_.id: input_.slot for input_ in group.inputs}
                for round_ in group.rounds:
                    for match in round_.matches:
                        slot1 = slot_of_input[assert_some(match.stage_item_input1_id)]
                        slot2 = slot_of_input[assert_some(match.stage_item_input2_id)]
                        response = await request(
                            HTTPMethod.PUT,
                            f"matches/{match.id}",
                            {
                                "round_id": round_.id,
                                "stage_item_input1_score": int(slot1 < slot2),
                                "stage_item_input2_score": int(slot2 < slot1),
                                "played": True,
                            },
                        )
                        assert response == SUCCESS_RESPONSE

            response = await request(
                HTTPMethod.POST,
                "playoffs",
                {
                    "group_stage_id": group_stage.id,
                    "stage_name": "Sluttspill",
                    "playoffs": [
                        {"name": "A", "placings": [1, 2], "third_place_match": True},
                        {"name": "B", "placings": [3, 4]},
                    ],
                },
            )
            assert response == SUCCESS_RESPONSE

            assert await request(HTTPMethod.POST, "stages/activate", {}) == SUCCESS_RESPONSE
            [_, playoff_stage] = await get_full_tournament_details(tournament_id)
            assert playoff_stage.name == "Sluttspill"
            assert first_round_team_names(playoff_stage, "A") == [["A1", "B2"], ["B1", "A2"]]
            assert first_round_team_names(playoff_stage, "B") == [["A3", "B4"], ["B3", "A4"]]
        finally:
            await delete_stages_except(auth_context, group_stage.id)


@pytest.mark.parametrize(
    ("playoffs", "error"),
    [
        pytest.param(
            [{"name": "A", "placings": [1, 5]}], "Group A only has 4 teams", id="no such placing"
        ),
        pytest.param(
            [{"name": "A", "placings": [1], "third_place_match": True}],
            "a third place match needs at least 4 teams",
            id="bronze with 1 group winner each",
        ),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_invalid_playoffs(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
    playoffs: list[JsonDict],
    error: str,
) -> None:
    tournament_id = auth_context.tournament.id
    async with inserted_stage(
        DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id})
    ) as group_stage:
        try:
            await create_groups(auth_context, group_stage.id, "AB")
            response = await send_tournament_request(
                HTTPMethod.POST,
                "playoffs",
                auth_context,
                json={"group_stage_id": group_stage.id, "playoffs": playoffs},
            )
            assert error in response["detail"]
        finally:
            await delete_stages_except(auth_context, group_stage.id)


@pytest.mark.asyncio(loop_scope="session")
async def test_overlapping_placings_rejected(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with inserted_stage(
        DUMMY_STAGE1.model_copy(update={"tournament_id": auth_context.tournament.id})
    ) as group_stage:
        response = await send_tournament_request(
            HTTPMethod.POST,
            "playoffs",
            auth_context,
            json={
                "group_stage_id": group_stage.id,
                "playoffs": [
                    {"name": "A", "placings": [1, 2]},
                    {"name": "B", "placings": [2, 3]},
                ],
            },
        )
    assert "Each placing can only go to one playoff" in str(response["detail"])


@pytest.mark.asyncio(loop_scope="session")
async def test_no_playoffs_in_classes_with_hidden_results(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    async with (
        inserted_category(
            CategoryInsertable(
                tournament_id=tournament_id,
                name="G10",
                created=DUMMY_MOCK_TIME,
                age=10,
                results_public=False,
            )
        ) as g10,
        inserted_stage(
            DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id, "category_id": g10.id})
        ) as group_stage,
    ):
        try:
            await create_groups(auth_context, group_stage.id, "A")
            response = await send_tournament_request(
                HTTPMethod.POST,
                "playoffs",
                auth_context,
                json={
                    "group_stage_id": group_stage.id,
                    "playoffs": [{"name": "A", "placings": [1, 2]}],
                },
            )
            assert "teams can't advance based on their placing" in response["detail"]
        finally:
            await delete_stages_except(auth_context, group_stage.id)


@pytest.mark.asyncio(loop_scope="session")
async def test_playoff_with_best_runner_up(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """
    3 groups of 3: the A playoff gets the 3 group winners and the best runner-up. The runner-up
    of group C has the best goal difference, so it takes the 4th place.
    """
    tournament_id = auth_context.tournament.id

    async def request(method: HTTPMethod, endpoint: str, json: JsonDict | None = None) -> JsonDict:
        return await send_tournament_request(method, endpoint, auth_context, json=json)

    async with AsyncExitStack() as stack:
        group_stage = await stack.enter_async_context(
            inserted_stage(DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id}))
        )
        teams = [
            await stack.enter_async_context(
                inserted_team(
                    DUMMY_TEAM1.model_copy(
                        update={"tournament_id": tournament_id, "name": f"{letter}{slot}"}
                    )
                )
            )
            for letter in "ABC"
            for slot in range(1, 4)
        ]
        try:
            for letter in "ABC":
                response = await request(
                    HTTPMethod.POST,
                    "stage_items",
                    {
                        "stage_id": group_stage.id,
                        "type": "ROUND_ROBIN",
                        "team_count": 3,
                        "name": f"Group {letter}",
                    },
                )
                assert response == SUCCESS_RESPONSE

            [stage] = await get_full_tournament_details(tournament_id)
            for group in stage.stage_items:
                letter = group.name[-1]
                for input_ in group.inputs:
                    [team] = [t for t in teams if t.name == f"{letter}{input_.slot}"]
                    response = await request(
                        HTTPMethod.PUT,
                        f"stage_items/{group.id}/inputs/{input_.id}",
                        {"team_id": team.id},
                    )
                    assert response == SUCCESS_RESPONSE

            [stage] = await get_full_tournament_details(tournament_id)
            for group in stage.stage_items:
                slot_of_input = {input_.id: input_.slot for input_ in group.inputs}
                for round_ in group.rounds:
                    for match in round_.matches:
                        slot1 = slot_of_input[assert_some(match.stage_item_input1_id)]
                        slot2 = slot_of_input[assert_some(match.stage_item_input2_id)]
                        # The lower slot wins 1-0, except C2 beats C3 5-0
                        margin = 5 if group.name == "Group C" and {slot1, slot2} == {2, 3} else 1
                        response = await request(
                            HTTPMethod.PUT,
                            f"matches/{match.id}",
                            {
                                "round_id": round_.id,
                                "stage_item_input1_score": margin if slot1 < slot2 else 0,
                                "stage_item_input2_score": margin if slot2 < slot1 else 0,
                                "played": True,
                            },
                        )
                        assert response == SUCCESS_RESPONSE

            response = await request(
                HTTPMethod.POST,
                "playoffs",
                {
                    "group_stage_id": group_stage.id,
                    "playoffs": [
                        {
                            "name": "A",
                            "placings": [1],
                            "best_of_placing": 2,
                            "best_ranks": [1],
                        }
                    ],
                },
            )
            assert response == SUCCESS_RESPONSE

            assert await request(HTTPMethod.POST, "stages/activate", {}) == SUCCESS_RESPONSE
            [_, playoff_stage] = await get_full_tournament_details(tournament_id)
            assert first_round_team_names(playoff_stage, "A") == [["A1", "C2"], ["B1", "C1"]]

            # Editing the "best runner-up" slot by hand replaces it completely: it becomes an
            # empty slot, not a broken one, also after going back to the group stage
            [playoff] = playoff_stage.stage_items
            [best_input] = [i for i in playoff.inputs if i.best_from_stage_id is not None]
            response = await request(
                HTTPMethod.PUT, f"stage_items/{playoff.id}/inputs/{best_input.id}", {}
            )
            assert response == SUCCESS_RESPONSE
            response = await request(HTTPMethod.POST, "stages/activate", {"direction": "previous"})
            assert response == SUCCESS_RESPONSE
            [_, playoff_stage] = await get_full_tournament_details(tournament_id)
            [edited] = [i for i in playoff_stage.stage_items[0].inputs if i.id == best_input.id]
            assert isinstance(edited, StageItemInputEmpty)

            # Choosing a group placing for it also gives a valid slot
            [group_b] = [g for g in stage.stage_items if g.name == "Group B"]
            response = await request(
                HTTPMethod.PUT,
                f"stage_items/{playoff.id}/inputs/{best_input.id}",
                {"winner_from_stage_item_id": group_b.id, "winner_position": 2},
            )
            assert response == SUCCESS_RESPONSE
            [_, playoff_stage] = await get_full_tournament_details(tournament_id)
            [edited] = [i for i in playoff_stage.stage_items[0].inputs if i.id == best_input.id]
            assert isinstance(edited, StageItemInputTentative)
            assert edited.best_from_stage_id is None

            # The database refuses a row that fits no kind of input
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                await database.execute(
                    "UPDATE stage_item_inputs SET winner_from_stage_item_id = NULL WHERE id = :id",
                    values={"id": best_input.id},
                )
        finally:
            await delete_stages_except(auth_context, group_stage.id)


@pytest.mark.parametrize(
    ("playoffs", "error"),
    [
        pytest.param(
            [{"name": "A", "placings": [1], "best_ranks": [1]}],
            "choose both the placing and which of the best teams",
            id="ranks without placing",
        ),
        pytest.param(
            [
                {"name": "A", "placings": [1], "best_of_placing": 2, "best_ranks": [1]},
                {"name": "B", "placings": [2]},
            ],
            "both completely and partly",
            id="placing in two ways",
        ),
        pytest.param(
            [
                {"name": "A", "placings": [1], "best_of_placing": 2, "best_ranks": [1]},
                {"name": "B", "placings": [3], "best_of_placing": 2, "best_ranks": [1, 2]},
            ],
            "Each of the best teams can only go to one playoff",
            id="same best team twice",
        ),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_invalid_best_of_playoffs(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
    playoffs: list[JsonDict],
    error: str,
) -> None:
    async with inserted_stage(
        DUMMY_STAGE1.model_copy(update={"tournament_id": auth_context.tournament.id})
    ) as group_stage:
        response = await send_tournament_request(
            HTTPMethod.POST,
            "playoffs",
            auth_context,
            json={"group_stage_id": group_stage.id, "playoffs": playoffs},
        )
    assert error in str(response["detail"])
