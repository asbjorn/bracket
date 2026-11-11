import pytest
from heliclockter import datetime_utc, timedelta

from bracket.database import database
from bracket.logic import score_entry
from bracket.schema import match_day_notices, score_links
from bracket.sql.courts import get_all_courts_in_tournament
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.teams import get_teams_with_members
from bracket.utils.http import HTTPMethod
from bracket.utils.id_types import TeamId
from bracket.utils.types import JsonDict, assert_some
from tests.integration_tests.api.cup_setup_test import G10, WINDOW, delete_cup
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    send_request,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext

TEAM_NAMES = ["Brann", "Lyn", "Fana", "Os", "Nest-Sotra", "Åsane"]


async def set_up_playable_cup(
    auth_context: AuthContext, cup_class: JsonDict = G10
) -> dict[str, TeamId]:
    """G10 (or another class) with six teams in two groups of three, planned on two courts."""
    body: JsonDict = {
        "classes": [cup_class],
        "courts": [{"count": 2, "name_prefix": "Bane", "game_format": "7v7"}],
        "time_windows": [WINDOW],
    }
    assert (
        await send_tournament_request(HTTPMethod.POST, "cup_setup", auth_context, json=body)
        == SUCCESS_RESPONSE
    )
    [stage] = await get_full_tournament_details(auth_context.tournament.id)
    category_id = assert_some(stage.category_id)
    response = await send_tournament_request(
        HTTPMethod.POST,
        "teams_multi",
        auth_context,
        json={"names": "\n".join(TEAM_NAMES), "active": True, "category_id": category_id},
    )
    assert response == SUCCESS_RESPONSE
    teams = await get_teams_with_members(auth_context.tournament.id, category_id=category_id)
    draw = await send_tournament_request(
        HTTPMethod.POST,
        f"stages/{stage.id}/draw",
        auth_context,
        json={"pots": [[team.id for team in teams]], "seed": 1},
    )
    assert len(draw["data"]) == 6
    plan = await send_tournament_request(HTTPMethod.POST, "schedule/apply", auth_context)
    assert plan["data"]["unscheduled_match_ids"] == []
    return {team.name: team.id for team in teams}


async def delete_score_links(auth_context: AuthContext) -> None:
    tournament_id = auth_context.tournament.id
    await database.execute(
        match_day_notices.delete().where(match_day_notices.c.tournament_id == tournament_id)
    )
    await database.execute(score_links.delete().where(score_links.c.tournament_id == tournament_id))


@pytest.mark.asyncio(loop_scope="session")
async def test_score_link_for_one_court(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    try:
        await set_up_playable_cup(auth_context)
        court1, court2 = await get_all_courts_in_tournament(tournament_id)
        created = await send_tournament_request(
            HTTPMethod.POST,
            "score_links",
            auth_context,
            json={"name": "Bane 1", "court_id": court1.id},
        )
        token = created["data"]["token"]
        link_id = created["data"]["link"]["id"]
        assert len(token) >= 40

        view = (await send_request(HTTPMethod.GET, f"score/{token}"))["data"]
        assert view["court_name"] == "Bane 1"
        matches = view["matches"]
        assert len(matches) == 3  # 6 group matches on two courts
        assert {m["court_id"] for m in matches} == {court1.id}
        assert [m["start_time"] for m in matches] == sorted(m["start_time"] for m in matches)
        first = matches[0]
        assert first["team1_name"] in {"Brann", "Lyn", "Fana", "Os", "Nest-Sotra", "Åsane"}
        assert first["category_name"] == "G10"

        # Enter a result
        result = {"score1": 2, "score2": 1}
        assert (
            await send_request(HTTPMethod.PUT, f"score/{token}/matches/{first['id']}", json=result)
            == SUCCESS_RESPONSE
        )
        view = (await send_request(HTTPMethod.GET, f"score/{token}"))["data"]
        assert (view["matches"][0]["score1"], view["matches"][0]["played"]) == (2, True)

        # Invalid results get the same checks as for the organiser
        walkover = {"score1": 1, "score2": 1, "result_type": "WALKOVER"}
        response = await send_request(
            HTTPMethod.PUT, f"score/{token}/matches/{first['id']}", json=walkover
        )
        assert "A walkover must have a winner" in str(response)

        # Matches on other courts can't be entered with this link
        [stage] = await get_full_tournament_details(tournament_id)
        other = next(
            m.id
            for item in stage.stage_items
            for r in item.rounds
            for m in r.matches
            if m.court_id == court2.id
        )
        response = await send_request(HTTPMethod.PUT, f"score/{token}/matches/{other}", json=result)
        assert response == {"detail": "This match can't be entered with this link"}

        # A delay reported from the pitch reaches the organiser
        notice = await send_request(
            HTTPMethod.POST, f"score/{token}/notices", json={"delay_minutes": 10}
        )
        assert notice["data"]["court_id"] == court1.id
        notices = await send_tournament_request(HTTPMethod.GET, "notices", auth_context)
        assert [(n["delay_minutes"], n["resolved"]) for n in notices["data"]] == [(10, False)]
        await send_tournament_request(
            HTTPMethod.POST, f"notices/{notice['data']['id']}/resolve", auth_context
        )
        notices = await send_tournament_request(HTTPMethod.GET, "notices", auth_context)
        assert notices["data"][0]["resolved"] is True

        # The list doesn't contain tokens; after revoking, the link stops working
        links = await send_tournament_request(HTTPMethod.GET, "score_links", auth_context)
        assert "token" not in links["data"][0] and "token_hash" not in links["data"][0]
        await send_tournament_request(
            HTTPMethod.POST, f"score_links/{link_id}/revoke", auth_context
        )
        response = await send_request(HTTPMethod.GET, f"score/{token}")
        assert "not valid" in response["detail"]
    finally:
        await delete_score_links(auth_context)
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_score_link_rules(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    try:
        await set_up_playable_cup(auth_context)
        created = await send_tournament_request(
            HTTPMethod.POST, "score_links", auth_context, json={"name": "Sekretariat"}
        )
        token = created["data"]["token"]
        view = (await send_request(HTTPMethod.GET, f"score/{token}"))["data"]
        assert len(view["matches"]) == 6
        assert view["court_id"] is None

        assert "not valid" in str(await send_request(HTTPMethod.GET, "score/wrong-token"))
        await database.execute(
            score_links.update()
            .where(score_links.c.tournament_id == tournament_id)
            .values(expires_at=datetime_utc.now() - timedelta(minutes=1))
        )
        assert "not valid" in str(await send_request(HTTPMethod.GET, f"score/{token}"))

        # A court of another tournament is rejected
        response = await send_tournament_request(
            HTTPMethod.POST, "score_links", auth_context, json={"name": "X", "court_id": 999999}
        )
        assert "detail" in response
        notice = await send_request(HTTPMethod.POST, "score/wrong-token/notices", json={})
        assert "detail" in notice
    finally:
        await delete_score_links(auth_context)
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_score_link_rate_limit(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """Wrong tokens are limited per client, valid links per link and client."""
    limiters = (score_entry.invalid_link_attempts, score_entry.score_link_writes)
    limits = [limiter.limit for limiter in limiters]
    for limiter in limiters:
        limiter.limit = 2
        limiter.hits.clear()  # Other tests used wrong tokens too
    try:
        body = {"delay_minutes": 5}
        responses = [
            await send_request(HTTPMethod.POST, f"score/wrong-token-{index}/notices", json=body)
            for index in range(3)
        ]
        assert [r["detail"][:20] for r in responses] == [
            "This link is not val",
            "This link is not val",
            "Too many requests, p",
        ]

        created = await send_tournament_request(
            HTTPMethod.POST, "score_links", auth_context, json={"name": "Alle"}
        )
        token = created["data"]["token"]
        responses = [
            await send_request(HTTPMethod.POST, f"score/{token}/notices", json=body)
            for _ in range(3)
        ]
        assert "data" in responses[0]
        assert "data" in responses[1]
        assert responses[2]["detail"].startswith("Too many requests")
        # Reading has its own, larger limit
        assert "data" in await send_request(HTTPMethod.GET, f"score/{token}")
    finally:
        for limiter, limit in zip(limiters, limits, strict=True):
            limiter.limit = limit
            limiter.hits.clear()
        await database.execute(
            match_day_notices.delete().where(
                match_day_notices.c.tournament_id == auth_context.tournament.id
            )
        )
        await database.execute(
            score_links.delete().where(score_links.c.tournament_id == auth_context.tournament.id)
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_score_link_valid_until_the_cup_is_over(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """By default a link works until a day after the last playing hours, and can be extended."""
    try:
        await set_up_playable_cup(auth_context)
        # The cup plays in ten days, 07:00-15:00 (UTC): valid until the day after, 15:00
        cup_day = (datetime_utc.now() + timedelta(days=10)).date().isoformat()
        hours = {
            "time_windows": [
                {"start_time": f"{cup_day}T07:00:00Z", "end_time": f"{cup_day}T15:00:00Z"}
            ]
        }
        saved = await send_tournament_request(
            HTTPMethod.PUT, "time_windows", auth_context, json=hours
        )
        assert len(saved["data"]) == 1
        created = await send_tournament_request(
            HTTPMethod.POST, "score_links", auth_context, json={"name": "Alle"}
        )
        link = created["data"]["link"]
        day_after = (datetime_utc.now() + timedelta(days=11)).date().isoformat()
        assert link["expires_at"] == f"{day_after}T15:00:00Z"

        until = (datetime_utc.now() + timedelta(days=3)).replace(microsecond=0)
        extended = await send_tournament_request(
            HTTPMethod.PUT,
            f"score_links/{link['id']}/validity",
            auth_context,
            json={"valid_until": until.isoformat()},
        )
        assert extended["data"]["expires_at"] == until.isoformat().replace("+00:00", "Z")
        # Same link: the token (and the QR code) keeps working
        assert extended["data"]["id"] == link["id"]

        past = await send_tournament_request(
            HTTPMethod.PUT,
            f"score_links/{link['id']}/validity",
            auth_context,
            json={"valid_until": "2020-01-01T00:00:00Z"},
        )
        assert "future" in str(past)

        revoke = await send_tournament_request(
            HTTPMethod.POST, f"score_links/{link['id']}/revoke", auth_context
        )
        assert revoke == SUCCESS_RESPONSE
        after_revoke = await send_tournament_request(
            HTTPMethod.PUT, f"score_links/{link['id']}/validity", auth_context, json={}
        )
        assert after_revoke == {"detail": "Could not find the link"}
    finally:
        await delete_score_links(auth_context)
        await delete_cup(auth_context)
