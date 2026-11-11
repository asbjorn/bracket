from contextlib import AsyncExitStack

import pytest

from bracket.models.db.util import StageItemWithRounds
from bracket.sql.shared import sql_delete_stage_item_with_foreign_keys
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.dummy_records import DUMMY_STAGE1, DUMMY_TEAM1
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import inserted_stage, inserted_team


async def get_bracket(auth_context: AuthContext) -> StageItemWithRounds:
    [stage] = await get_full_tournament_details(auth_context.tournament.id)
    [stage_item] = stage.stage_items
    return stage_item


@pytest.mark.asyncio(loop_scope="session")
async def test_knockout_with_byes_and_third_place_match(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """
    6 teams: slots 1+2 and 4+5 play the first round, slots 0 and 3 have a bye. The losers of
    the semifinals play for third place.
    """
    tournament_id = auth_context.tournament.id
    async with AsyncExitStack() as stack:
        stage = await stack.enter_async_context(
            inserted_stage(DUMMY_STAGE1.model_copy(update={"tournament_id": tournament_id}))
        )
        teams = [
            await stack.enter_async_context(
                inserted_team(
                    DUMMY_TEAM1.model_copy(
                        update={"tournament_id": tournament_id, "name": f"Team {slot}"}
                    )
                )
            )
            for slot in range(6)
        ]
        response = await send_tournament_request(
            HTTPMethod.POST,
            "stage_items",
            auth_context,
            json={
                "stage_id": stage.id,
                "type": "SINGLE_ELIMINATION",
                "team_count": 6,
                "third_place_match": True,
            },
        )
        assert response == SUCCESS_RESPONSE
        bracket = await get_bracket(auth_context)

        try:
            inputs = sorted(bracket.inputs, key=lambda i: i.slot)
            for input_, team in zip(inputs, teams, strict=True):
                assert (
                    await send_tournament_request(
                        HTTPMethod.PUT,
                        f"stage_items/{bracket.id}/inputs/{input_.id}",
                        auth_context,
                        json={"team_id": team.id},
                    )
                    == SUCCESS_RESPONSE
                )

            async def play(match_id: int, round_id: int, score1: int, score2: int) -> None:
                result = await send_tournament_request(
                    HTTPMethod.PUT,
                    f"matches/{match_id}",
                    auth_context,
                    json={
                        "round_id": round_id,
                        "stage_item_input1_score": score1,
                        "stage_item_input2_score": score2,
                        "played": True,
                    },
                )
                assert result == SUCCESS_RESPONSE

            def team_names(stage_item: StageItemWithRounds) -> list[list[tuple[str, str]]]:
                def name(input_: object) -> str:
                    team = getattr(input_, "team", None)
                    return team.name if team is not None else "?"

                return [
                    [
                        (name(m.stage_item_input1), name(m.stage_item_input2))
                        for m in sorted(round_.matches, key=lambda m: m.id)
                    ]
                    for round_ in sorted(stage_item.rounds, key=lambda r: r.id)
                ]

            bracket = await get_bracket(auth_context)
            assert team_names(bracket) == [
                [("Team 1", "Team 2"), ("Team 4", "Team 5")],
                [("Team 0", "?"), ("Team 3", "?")],
                [("?", "?"), ("?", "?")],
            ]

            # First round: Team 1 and Team 5 win
            rounds = sorted(bracket.rounds, key=lambda r: r.id)
            first, second = sorted(rounds[0].matches, key=lambda m: m.id)
            await play(first.id, rounds[0].id, 2, 0)
            await play(second.id, rounds[0].id, 0, 1)

            # Semifinals: Team 0 beats Team 1, Team 5 beats Team 3 on penalties
            bracket = await get_bracket(auth_context)
            rounds = sorted(bracket.rounds, key=lambda r: r.id)
            assert team_names(bracket)[1] == [("Team 0", "Team 1"), ("Team 3", "Team 5")]
            semi1, semi2 = sorted(rounds[1].matches, key=lambda m: m.id)
            await play(semi1.id, rounds[1].id, 3, 1)
            result = await send_tournament_request(
                HTTPMethod.PUT,
                f"matches/{semi2.id}",
                auth_context,
                json={
                    "round_id": rounds[1].id,
                    "stage_item_input1_score": 1,
                    "stage_item_input2_score": 1,
                    "result_type": "PENALTIES",
                    "stage_item_input1_penalties": 2,
                    "stage_item_input2_penalties": 4,
                    "played": True,
                },
            )
            assert result == SUCCESS_RESPONSE

            # Final: Team 0 vs Team 5; third place: Team 1 vs Team 3
            bracket = await get_bracket(auth_context)
            assert team_names(bracket)[2] == [("Team 0", "Team 5"), ("Team 1", "Team 3")]
        finally:
            await sql_delete_stage_item_with_foreign_keys(bracket.id)
