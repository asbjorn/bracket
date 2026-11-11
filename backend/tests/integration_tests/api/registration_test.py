from datetime import timedelta

import aiohttp
import pytest
from heliclockter import datetime_utc

from bracket.database import database
from bracket.routes.registrations import public_sign_ups
from bracket.schema import tournaments, users
from bracket.utils.http import HTTPMethod
from bracket.utils.types import JsonDict
from tests.integration_tests.api.cup_setup_test import G10, delete_cup
from tests.integration_tests.api.public_info_test import set_dashboard_public
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    get_root_uvicorn_url,
    send_request,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext

EMAIL = "kari.nordmann@example.org"


def sign_up(category_id: int, team_name: str, **changes: object) -> JsonDict:
    return {
        "category_id": category_id,
        "team_name": team_name,
        "club_name": None,
        "contact_name": "Kari Nordmann",
        "contact_email": EMAIL,
        "contact_phone": "+47 912 34 567",
        "comment": None,
        "consent": True,
        "website": "",
    } | changes


async def create_class(auth_context: AuthContext, settings: JsonDict) -> int:
    body: JsonDict = {"classes": [G10], "time_windows": []}
    response = await send_tournament_request(HTTPMethod.POST, "cup_setup", auth_context, json=body)
    assert response == SUCCESS_RESPONSE
    categories = await send_tournament_request(HTTPMethod.GET, "categories", auth_context)
    [category] = categories["data"]
    response = await send_tournament_request(
        HTTPMethod.PUT,
        f"categories/{category['id']}/registration",
        auth_context,
        json={"registration_deadline": None, "max_teams": None, "entry_fee": None} | settings,
    )
    assert response == SUCCESS_RESPONSE
    return int(category["id"])


async def public_post(tournament_id: int, body: JsonDict) -> JsonDict:
    return await send_request(
        HTTPMethod.POST, f"tournaments/{tournament_id}/registration", json=body
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_sign_up_waitlist_and_promote(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    public_sign_ups.hits.clear()
    try:
        category_id = await create_class(
            auth_context, {"registration_open": True, "max_teams": 2, "entry_fee": 1500}
        )
        classes = await send_request(
            HTTPMethod.GET, f"tournaments/{tournament_id}/registration/classes"
        )
        assert [(c["name"], c["spots_left"], c["entry_fee"]) for c in classes["data"]] == [
            ("G10", 2, 1500)
        ]

        results = [
            (await public_post(tournament_id, sign_up(category_id, name)))["data"]
            for name in ("Brann 1", "Brann 2", "Lyn", "Fana")
        ]
        assert [(r["registration_status"], r["waitlist_place"]) for r in results] == [
            ("REGISTERED", None),
            ("REGISTERED", None),
            ("WAITLIST", 1),
            ("WAITLIST", 2),
        ]
        duplicate = await public_post(tournament_id, sign_up(category_id, "brann 1"))
        assert duplicate == {"detail": "A team with this name is already registered in this class"}

        # Contact details only for the organiser
        teams = await send_tournament_request(HTTPMethod.GET, "teams", auth_context)
        assert EMAIL not in str(teams)
        assert sorted(t["name"] for t in teams["data"]["teams"]) == ["Brann 1", "Brann 2"]
        stages = await send_request(HTTPMethod.GET, f"tournaments/{tournament_id}/stages")
        assert EMAIL not in str(stages)
        registrations = await send_tournament_request(HTTPMethod.GET, "registrations", auth_context)
        rows = {r["team_name"]: r for r in registrations["data"]}
        assert rows["Lyn"]["contact_email"] == EMAIL
        assert rows["Fana"]["waitlist_place"] == 2
        unauthenticated = await send_request(
            HTTPMethod.GET, f"tournaments/{tournament_id}/registrations"
        )
        assert EMAIL not in str(unauthenticated)

        # Waitlisted teams can't be drawn
        stages = await send_tournament_request(HTTPMethod.GET, "stages", auth_context)
        group_stage_id = stages["data"][0]["id"]
        draw = await send_tournament_request(
            HTTPMethod.POST,
            f"stages/{group_stage_id}/draw",
            auth_context,
            json={"pots": [[rows["Lyn"]["team_id"]]], "seed": 1},
        )
        assert draw == {"detail": "Teams on the waitlist or rejected teams can't be drawn"}

        # A team drops out: the first on the waitlist moves up
        response = await send_tournament_request(
            HTTPMethod.PUT,
            f"registrations/{rows['Brann 2']['team_id']}",
            auth_context,
            json={
                "registration_status": "REJECTED",
                "paid": False,
                "squad_reported": False,
                "contact_name": None,
                "contact_email": None,
                "contact_phone": None,
                "comment": "Trakk seg",
            },
        )
        assert response == SUCCESS_RESPONSE
        response = await send_tournament_request(
            HTTPMethod.POST, f"categories/{category_id}/waitlist/promote", auth_context
        )
        assert response == SUCCESS_RESPONSE
        registrations = await send_tournament_request(HTTPMethod.GET, "registrations", auth_context)
        statuses = {r["team_name"]: r["registration_status"] for r in registrations["data"]}
        assert statuses == {
            "Brann 1": "REGISTERED",
            "Brann 2": "REJECTED",
            "Lyn": "APPROVED",
            "Fana": "WAITLIST",
        }
        fana = next(r for r in registrations["data"] if r["team_name"] == "Fana")
        assert fana["waitlist_place"] == 1

        # A team in a group can't leave the cup before it's taken out of the group
        brann_1 = rows["Brann 1"]["team_id"]
        draw = await send_tournament_request(
            HTTPMethod.POST,
            f"stages/{group_stage_id}/draw",
            auth_context,
            json={"pots": [[brann_1]], "seed": 1},
        )
        assert len(draw["data"]) == 1
        rejected = await send_tournament_request(
            HTTPMethod.PUT,
            f"registrations/{brann_1}",
            auth_context,
            json={
                "registration_status": "WAITLIST",
                "paid": True,
                "squad_reported": False,
                "contact_name": None,
                "contact_email": None,
                "contact_phone": None,
                "comment": None,
            },
        )
        assert rejected == {
            "detail": "The team is placed in a group; remove it there before it leaves the cup"
        }
    finally:
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_sign_up_closed_deadline_and_abuse(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    public_sign_ups.hits.clear()
    try:
        yesterday = (datetime_utc.now() - timedelta(days=1)).isoformat()
        category_id = await create_class(
            auth_context, {"registration_open": True, "registration_deadline": yesterday}
        )
        late = await public_post(tournament_id, sign_up(category_id, "Lyn"))
        assert late == {"detail": "Registration for this class is closed"}
        classes = await send_request(
            HTTPMethod.GET, f"tournaments/{tournament_id}/registration/classes"
        )
        assert classes == {"data": []}

        no_consent = await public_post(tournament_id, sign_up(category_id, "Lyn", consent=False))
        assert "consent" in str(no_consent)
        bad_phone = await public_post(
            tournament_id, sign_up(category_id, "Lyn", contact_phone="call me")
        )
        assert "contact_phone" in str(bad_phone)

        # Bots fill in the hidden field: they get an answer, nothing is stored
        bot = await public_post(tournament_id, sign_up(category_id, "Spam", website="x"))
        assert bot["data"]["registration_status"] == "REGISTERED"
        count = await database.fetch_val(
            "SELECT count(*) FROM teams WHERE tournament_id = :id AND name = 'Spam'",
            values={"id": tournament_id},
        )
        assert count == 0

        # At most 10 sign-ups per hour per client (2 used above; invalid forms are rejected
        # before they count)
        for _ in range(8):
            await public_post(tournament_id, sign_up(category_id, "Lyn"))
        limited = await public_post(tournament_id, sign_up(category_id, "Lyn"))
        assert limited == {"detail": "Too many requests, please wait a moment and try again"}

        # Not for cups that aren't public
        public_sign_ups.hits.clear()
        await set_dashboard_public(tournament_id, False)
        hidden = await public_post(tournament_id, sign_up(category_id, "Lyn"))
        assert "not publicly available" in str(hidden)
    finally:
        await set_dashboard_public(tournament_id, True)
        public_sign_ups.hits.clear()
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_registrations_csv(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    public_sign_ups.hits.clear()
    try:
        category_id = await create_class(auth_context, {"registration_open": True})
        result = await public_post(
            tournament_id, sign_up(category_id, "=HYPERLINK(1)", comment="@SUM(A1)")
        )
        assert result["data"]["registration_status"] == "REGISTERED"

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{get_root_uvicorn_url()}tournaments/{tournament_id}/registrations.csv",
                params={"language": "nb"},
                headers=auth_context.headers,
            ) as resp,
        ):
            assert resp.headers["Content-Type"] == "text/csv; charset=utf-8"
            text = (await resp.read()).decode("utf-8")
        assert text.startswith('﻿"Klasse";"Lag";"Klubb";"Status"')
        assert '"G10";"\'=HYPERLINK(1)";"";"REGISTERED";"";"Kari Nordmann";"' + EMAIL in text
        assert ';"\'@SUM(A1)";' in text
        assert text.endswith('"Nei";"Nei";"Nei"\r\n')
    finally:
        public_sign_ups.hits.clear()
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_sign_up_respects_archive_and_subscription(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    user_id = auth_context.user.id
    public_sign_ups.hits.clear()
    try:
        category_id = await create_class(auth_context, {"registration_open": True})

        # An archived cup takes no sign-ups and shows no open classes
        await database.execute(
            tournaments.update().where(tournaments.c.id == tournament_id),
            values={"status": "ARCHIVED"},
        )
        classes = await send_request(
            HTTPMethod.GET, f"tournaments/{tournament_id}/registration/classes"
        )
        assert classes == {"data": []}
        archived = await public_post(tournament_id, sign_up(category_id, "Lyn"))
        assert archived == {"detail": "Can't update archived tournament"}
        await database.execute(
            tournaments.update().where(tournaments.c.id == tournament_id),
            values={"status": "OPEN"},
        )

        # The owner's subscription limits the teams, also those that sign up themselves
        await database.execute(
            users.update().where(users.c.id == user_id), values={"account_type": "DEMO"}
        )
        existing = int(
            await database.fetch_val(
                "SELECT count(*) FROM teams WHERE tournament_id = :id", values={"id": tournament_id}
            )
        )
        allowed = 8 - existing
        results = [
            await public_post(tournament_id, sign_up(category_id, f"Lag {number}"))
            for number in range(allowed + 1)
        ]
        assert [("data" in result) for result in results] == [True] * allowed + [False]
        assert results[-1] == {"detail": "Your `DEMO` subscription allows a maximum of 8 teams."}
    finally:
        await database.execute(
            users.update().where(users.c.id == user_id), values={"account_type": "REGULAR"}
        )
        await database.execute(
            tournaments.update().where(tournaments.c.id == tournament_id),
            values={"status": "OPEN"},
        )
        public_sign_ups.hits.clear()
        await delete_cup(auth_context)
