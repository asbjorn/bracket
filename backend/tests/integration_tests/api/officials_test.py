import aiohttp
import pytest

from bracket.utils.http import HTTPMethod
from bracket.utils.types import JsonDict
from tests.integration_tests.api.cup_setup_test import G10, WINDOW, delete_cup
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    get_root_uvicorn_url,
    send_request,
    send_tournament_request,
)
from tests.integration_tests.models import AuthContext

EMAIL = "ola.dommer@example.org"


async def planned_cup(auth_context: AuthContext) -> list[JsonDict]:
    """G10 (6 matches) on two 7v7 courts, planned: the scheduled matches."""
    body: JsonDict = {
        "classes": [G10],
        "courts": [{"count": 2, "name_prefix": "Bane", "game_format": "7v7"}],
        "time_windows": [WINDOW],
    }
    assert (
        await send_tournament_request(HTTPMethod.POST, "cup_setup", auth_context, json=body)
        == SUCCESS_RESPONSE
    )
    proposal = await send_tournament_request(HTTPMethod.POST, "schedule/apply", auth_context)
    assert proposal["data"]["unscheduled_match_ids"] == []
    return sorted(proposal["data"]["matches"], key=lambda m: (m["start_time"], m["court_id"]))


async def create_official(auth_context: AuthContext, name: str, **changes: object) -> int:
    body: JsonDict = {
        "name": name,
        "age": 17,
        "level": "Klubbdommer",
        "club_name": None,
        "phone": "+47 900 00 000",
        "email": EMAIL,
        "role": "REFEREE",
        "fee_per_match": 150,
        "fee_per_day": 0,
        "active": True,
    } | changes
    response = await send_tournament_request(HTTPMethod.POST, "officials", auth_context, json=body)
    return int(response["data"]["id"])


@pytest.mark.asyncio(loop_scope="session")
async def test_officials(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    try:
        matches = await planned_cup(auth_context)
        # The first two matches are at the same time on the two courts
        first, second = matches[0], matches[1]
        assert first["start_time"] == second["start_time"]
        ola = await create_official(auth_context, "Ola")
        kari = await create_official(auth_context, "Kari", fee_per_day=300)

        response = await send_tournament_request(
            HTTPMethod.PUT,
            f"matches/{first['match_id']}/officials",
            auth_context,
            json={"referee_id": ola, "assistant_ids": [kari]},
        )
        assert response == SUCCESS_RESPONSE
        response = await send_tournament_request(
            HTTPMethod.PUT,
            f"matches/{second['match_id']}/officials",
            auth_context,
            json={"referee_id": ola, "assistant_ids": []},
        )
        assert response == SUCCESS_RESPONSE

        overview = (await send_tournament_request(HTTPMethod.GET, "officials", auth_context))[
            "data"
        ]
        assert [(c["official_id"], c["kind"]) for c in overview["conflicts"]] == [
            (ola, "DOUBLE_BOOKED")
        ]
        fees = {f["name"]: (f["matches"], f["days"], f["total"]) for f in overview["fees"]}
        assert fees == {"Kari": (1, 1, 150 + 300), "Ola": (2, 1, 300)}

        # A whole court block for Kari: she becomes referee there, Ola stays only on court 2
        court1 = first["court_id"]
        response = await send_tournament_request(
            HTTPMethod.POST,
            "officials/assign_block",
            auth_context,
            json={
                "official_id": kari,
                "court_id": court1,
                "start_time": "2026-06-13T00:00:00Z",
                "end_time": "2026-06-14T00:00:00Z",
            },
        )
        assert response == SUCCESS_RESPONSE
        overview = (await send_tournament_request(HTTPMethod.GET, "officials", auth_context))[
            "data"
        ]
        on_court1 = {m["match_id"] for m in matches if m["court_id"] == court1}
        referees = {
            a["match_id"]: a["official_id"]
            for a in overview["assignments"]
            if a["role"] == "REFEREE"
        }
        assert all(referees[match_id] == kari for match_id in on_court1)
        assert overview["conflicts"] == []

        # Kampvert on court 2 during Ola's match: a double booking
        response = await send_tournament_request(
            HTTPMethod.POST,
            "court_hosts",
            auth_context,
            json={
                "official_id": ola,
                "court_id": second["court_id"],
                "start_time": second["start_time"],
                "end_time": "2026-06-13T15:00:00Z",
            },
        )
        assert response == SUCCESS_RESPONSE
        overview = (await send_tournament_request(HTTPMethod.GET, "officials", auth_context))[
            "data"
        ]
        assert [c["kind"] for c in overview["conflicts"]] == ["DOUBLE_BOOKED"]

        # Names only in public
        public = await send_request(HTTPMethod.GET, f"tournaments/{tournament_id}/match_officials")
        assert {"match_id": second["match_id"], "name": "Ola", "role": "REFEREE"} in public["data"]
        assert EMAIL not in str(public) and "+47" not in str(public)

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{get_root_uvicorn_url()}tournaments/{tournament_id}/officials_fees.csv",
                params={"language": "nb"},
                headers=auth_context.headers,
            ) as resp,
        ):
            text = (await resp.read()).decode("utf-8")
        assert text.startswith('﻿"Navn";"Nivå"')

        # Wrong ids
        missing = await send_tournament_request(
            HTTPMethod.PUT,
            "matches/999999/officials",
            auth_context,
            json={"referee_id": ola, "assistant_ids": []},
        )
        assert missing == {"detail": "Could not find the match"}
        both = await send_tournament_request(
            HTTPMethod.PUT,
            f"matches/{first['match_id']}/officials",
            auth_context,
            json={"referee_id": ola, "assistant_ids": [ola]},
        )
        assert "only have one role" in str(both)

        # Deleting an official removes their assignments
        assert (
            await send_tournament_request(HTTPMethod.DELETE, f"officials/{kari}", auth_context)
            == SUCCESS_RESPONSE
        )
        overview = (await send_tournament_request(HTTPMethod.GET, "officials", auth_context))[
            "data"
        ]
        assert {a["official_id"] for a in overview["assignments"]} == {ola}
    finally:
        await delete_cup(auth_context)
