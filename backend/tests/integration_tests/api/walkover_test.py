import pytest

from bracket.models.db.match import (
    MatchResultType,
    MatchWithDetails,
    MatchWithDetailsDefinitive,
)
from bracket.models.db.stage_item_inputs import StageItemInputFinal
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.teams import get_team_by_id
from bracket.utils.http import HTTPMethod
from bracket.utils.id_types import TeamId
from bracket.utils.types import assert_some
from tests.integration_tests.api.cup_setup_test import delete_cup
from tests.integration_tests.api.score_links_test import delete_score_links, set_up_playable_cup
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    send_request,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext


def team_id(input_: object) -> TeamId | None:
    return input_.team.id if isinstance(input_, StageItemInputFinal) else None


def teams_of(match: MatchWithDetails | MatchWithDetailsDefinitive) -> set[TeamId | None]:
    return {team_id(match.stage_item_input1), team_id(match.stage_item_input2)}


async def matches_of(
    auth_context: AuthContext, team: TeamId
) -> list[MatchWithDetails | MatchWithDetailsDefinitive]:
    [stage] = await get_full_tournament_details(auth_context.tournament.id)
    return [
        match
        for item in stage.stage_items
        for round_ in item.rounds
        for match in round_.matches
        if team in teams_of(match)
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_walkover_and_withdraw(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    try:
        teams = await set_up_playable_cup(auth_context)
        brann = teams["Brann"]
        [first, second] = await matches_of(auth_context, brann)

        # Walkover for Brann in its first match: 3-0 by default
        response = await send_tournament_request(
            HTTPMethod.POST,
            f"matches/{first.id}/walkover",
            auth_context,
            json={"winner_team_id": brann},
        )
        assert response == SUCCESS_RESPONSE
        [first, second] = await matches_of(auth_context, brann)
        brann_first = team_id(first.stage_item_input1) == brann
        scores = (first.stage_item_input1_score, first.stage_item_input2_score)
        assert scores == ((3, 0) if brann_first else (0, 3))
        assert (first.result_type, first.played) == (MatchResultType.WALKOVER, True)

        # Only one of the two teams can win the walkover
        response = await send_tournament_request(
            HTTPMethod.POST,
            f"matches/{second.id}/walkover",
            auth_context,
            json={"winner_team_id": next(t for t in teams.values() if t not in teams_of(second))},
        )
        assert response == {"detail": "The winner of a walkover must be one of the two teams"}

        # Brann withdraws: its remaining match goes to the opponent, the played one stays
        withdrawn = await send_tournament_request(
            HTTPMethod.POST, f"teams/{brann}/withdraw", auth_context
        )
        assert withdrawn == {"data": 1}
        [first, second] = await matches_of(auth_context, brann)
        assert first.result_type is MatchResultType.WALKOVER
        assert second.result_type is MatchResultType.WALKOVER and second.played
        brann_first = team_id(second.stage_item_input1) == brann
        scores = (second.stage_item_input1_score, second.stage_item_input2_score)
        assert scores == ((0, 3) if brann_first else (3, 0))
        assert assert_some(await get_team_by_id(brann, auth_context.tournament.id)).withdrawn

        await send_tournament_request(HTTPMethod.POST, f"teams/{brann}/reinstate", auth_context)
        assert not assert_some(await get_team_by_id(brann, auth_context.tournament.id)).withdrawn
    finally:
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_check_in_and_walkover_with_score_link(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    try:
        teams = await set_up_playable_cup(auth_context)
        # Organiser checks in Lyn
        response = await send_tournament_request(
            HTTPMethod.PUT,
            f"teams/{teams['Lyn']}/check_in",
            auth_context,
            json={"checked_in": True},
        )
        assert response == SUCCESS_RESPONSE
        assert assert_some(await get_team_by_id(teams["Lyn"], tournament_id)).checked_in

        created = await send_tournament_request(
            HTTPMethod.POST, "score_links", auth_context, json={"name": "Sekretariat"}
        )
        token = created["data"]["token"]
        view = (await send_request(HTTPMethod.GET, f"score/{token}"))["data"]
        assert view["walkover_goals"] == 3
        lyn_match = next(
            m for m in view["matches"] if teams["Lyn"] in (m["team1_id"], m["team2_id"])
        )
        lyn_is_team1 = lyn_match["team1_id"] == teams["Lyn"]
        assert lyn_match["team1_checked_in" if lyn_is_team1 else "team2_checked_in"] is True
        other = lyn_match["team2_id"] if lyn_is_team1 else lyn_match["team1_id"]

        # At the pitch: check in the other team, then give Lyn a walkover
        response = await send_request(
            HTTPMethod.PUT, f"score/{token}/teams/{other}/check_in", json={"checked_in": True}
        )
        assert response == SUCCESS_RESPONSE
        response = await send_request(
            HTTPMethod.PUT,
            f"score/{token}/matches/{lyn_match['id']}/walkover",
            json={"winner_team_id": teams["Lyn"]},
        )
        assert response == SUCCESS_RESPONSE
        view = (await send_request(HTTPMethod.GET, f"score/{token}"))["data"]
        entered = next(m for m in view["matches"] if m["id"] == lyn_match["id"])
        assert entered["result_type"] == "WALKOVER"
        assert (entered["score1"], entered["score2"]) == ((3, 0) if lyn_is_team1 else (0, 3))
        assert entered["team1_checked_in"] and entered["team2_checked_in"]

        response = await send_request(
            HTTPMethod.PUT, f"score/{token}/teams/999999/check_in", json={"checked_in": True}
        )
        assert response == {"detail": "This team can't be checked in with this link"}
    finally:
        await delete_score_links(auth_context)
        await delete_cup(auth_context)
