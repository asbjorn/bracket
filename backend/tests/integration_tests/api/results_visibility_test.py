from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import NamedTuple

import pytest

from bracket.database import database
from bracket.models.db.category import CategoryInsertable
from bracket.models.db.match import Match
from bracket.models.db.stage_item_inputs import StageItemInputInsertable
from bracket.schema import matches
from bracket.utils.db import fetch_one_parsed_certain
from bracket.utils.dummy_records import (
    DUMMY_COURT1,
    DUMMY_MATCH1,
    DUMMY_MOCK_TIME,
    DUMMY_ROUND1,
    DUMMY_STAGE1,
    DUMMY_STAGE_ITEM1,
    DUMMY_TEAM1,
)
from bracket.utils.http import HTTPMethod
from bracket.utils.id_types import MatchId, RoundId, StageItemInputId
from bracket.utils.types import JsonDict
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    send_request,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import (
    inserted_category,
    inserted_court,
    inserted_match,
    inserted_round,
    inserted_stage,
    inserted_stage_item,
    inserted_stage_item_input,
    inserted_team,
)


class ClassWithPlayedMatch(NamedTuple):
    match_id: MatchId
    round_id: RoundId
    input_ids: tuple[StageItemInputId, StageItemInputId]


@asynccontextmanager
async def inserted_class_with_played_match(
    auth_context: AuthContext, name: str, *, results_public: bool
) -> AsyncIterator[ClassWithPlayedMatch]:
    """
    A class with one stage, one group of two teams and one played match that ended 3-1.
    """
    tournament_id = auth_context.tournament.id
    async with AsyncExitStack() as stack:
        category = await stack.enter_async_context(
            inserted_category(
                CategoryInsertable(
                    tournament_id=tournament_id,
                    name=name,
                    created=DUMMY_MOCK_TIME,
                    results_public=results_public,
                )
            )
        )
        stage = await stack.enter_async_context(
            inserted_stage(
                DUMMY_STAGE1.model_copy(
                    update={"tournament_id": tournament_id, "category_id": category.id}
                )
            )
        )
        stage_item = await stack.enter_async_context(
            inserted_stage_item(
                DUMMY_STAGE_ITEM1.model_copy(
                    update={"stage_id": stage.id, "ranking_id": auth_context.ranking.id}
                )
            )
        )
        round_ = await stack.enter_async_context(
            inserted_round(DUMMY_ROUND1.model_copy(update={"stage_item_id": stage_item.id}))
        )
        inputs = []
        for slot in (0, 1):
            team = await stack.enter_async_context(
                inserted_team(
                    DUMMY_TEAM1.model_copy(
                        update={
                            "name": f"{name} team {slot}",
                            "tournament_id": tournament_id,
                            "category_id": category.id,
                        }
                    )
                )
            )
            inputs.append(
                await stack.enter_async_context(
                    inserted_stage_item_input(
                        StageItemInputInsertable(
                            slot=slot,
                            team_id=team.id,
                            tournament_id=tournament_id,
                            stage_item_id=stage_item.id,
                        )
                    )
                )
            )
        court = await stack.enter_async_context(
            inserted_court(DUMMY_COURT1.model_copy(update={"tournament_id": tournament_id}))
        )
        match = await stack.enter_async_context(
            inserted_match(
                DUMMY_MATCH1.model_copy(
                    update={
                        "round_id": round_.id,
                        "stage_item_input1_id": inputs[0].id,
                        "stage_item_input2_id": inputs[1].id,
                        "court_id": court.id,
                        "stage_item_input1_score": 3,
                        "stage_item_input2_score": 1,
                        "played": True,
                    }
                )
            )
        )
        await database.execute(
            "UPDATE stage_item_inputs SET points = 3, wins = 1 WHERE id = :id",
            values={"id": inputs[0].id},
        )
        yield ClassWithPlayedMatch(match.id, round_.id, (inputs[0].id, inputs[1].id))


def find_match(response: JsonDict, match_id: MatchId) -> JsonDict:
    return next(
        match
        for stage in response["data"]
        for stage_item in stage["stage_items"]
        for round_ in stage_item["rounds"]
        for match in round_["matches"]
        if match["id"] == match_id
    )


def find_input(response: JsonDict, input_id: StageItemInputId) -> JsonDict:
    return next(
        input_
        for stage in response["data"]
        for stage_item in stage["stage_items"]
        for input_ in stage_item["inputs"]
        if input_["id"] == input_id
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_public_dashboard_hides_results_of_private_classes(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with (
        inserted_class_with_played_match(auth_context, "G10", results_public=False) as g10,
        inserted_class_with_played_match(auth_context, "J14", results_public=True) as j14,
    ):
        endpoint = f"tournaments/{auth_context.tournament.id}/stages?no_draft_rounds=true"
        public = await send_request(HTTPMethod.GET, endpoint)
        organiser = await send_request(HTTPMethod.GET, endpoint, headers=auth_context.headers)

    # Children's class: public sees that the match was played, but not the score or the table
    public_g10_match = find_match(public, g10.match_id)
    assert public_g10_match["played"] is True
    assert public_g10_match["stage_item_input1_score"] == 0
    assert public_g10_match["stage_item_input2_score"] == 0
    assert public_g10_match["stage_item_input1"]["points"] == "0.0"
    assert public_g10_match["stage_item_input1"]["wins"] == 0
    assert find_input(public, g10.input_ids[0])["points"] == "0.0"
    assert find_input(public, g10.input_ids[0])["wins"] == 0

    # Youth class: everything is public
    public_j14_match = find_match(public, j14.match_id)
    assert public_j14_match["stage_item_input1_score"] == 3
    assert public_j14_match["stage_item_input2_score"] == 1
    assert find_input(public, j14.input_ids[0])["wins"] == 1

    # The organiser always sees the results
    organiser_g10_match = find_match(organiser, g10.match_id)
    assert organiser_g10_match["stage_item_input1_score"] == 3
    assert organiser_g10_match["stage_item_input2_score"] == 1
    assert find_input(organiser, g10.input_ids[0])["wins"] == 1


@pytest.mark.parametrize(
    ("previously_played", "body", "expected_played"),
    [
        pytest.param(False, {"stage_item_input1_score": 2}, True, id="entering a score"),
        pytest.param(False, {}, False, id="0-0 without played flag"),
        pytest.param(False, {"played": True}, True, id="played without score"),
        pytest.param(True, {}, True, id="stays played"),
        pytest.param(True, {"stage_item_input1_score": 2, "played": False}, False, id="unset"),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_update_match_played(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
    previously_played: bool,
    body: JsonDict,
    expected_played: bool,
) -> None:
    async with inserted_class_with_played_match(auth_context, "G10", results_public=False) as g10:
        await database.execute(
            "UPDATE matches SET played = :played, stage_item_input1_score = 0, "
            "stage_item_input2_score = 0 WHERE id = :id",
            values={"id": g10.match_id, "played": previously_played},
        )
        response = await send_tournament_request(
            HTTPMethod.PUT,
            f"matches/{g10.match_id}",
            auth_context,
            json={"round_id": g10.round_id, **body},
        )
        assert response == SUCCESS_RESPONSE

        match = await fetch_one_parsed_certain(
            database, Match, matches.select().where(matches.c.id == g10.match_id)
        )
        assert match.played is expected_played
