import pytest

from bracket.database import database
from bracket.schema import jury_decisions, jury_members
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
from tests.integration_tests.models import AuthContext


async def clean_up(auth_context: AuthContext) -> None:
    tournament_id = auth_context.tournament.id
    await database.execute(
        jury_decisions.delete().where(jury_decisions.c.tournament_id == tournament_id)
    )
    await database.execute(
        jury_members.delete().where(jury_members.c.tournament_id == tournament_id)
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_jury_members_and_decisions(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    try:
        for body in (
            {"name": "Kari", "club_name": "Brann", "role": "CHAIR", "phone": "+47 900 00 001"},
            {"name": "Ola", "club_name": "Brann"},
        ):
            response = await send_tournament_request(
                HTTPMethod.POST, "jury_members", auth_context, json=body
            )
            assert response == SUCCESS_RESPONSE
        overview = (await send_tournament_request(HTTPMethod.GET, "jury_members", auth_context))[
            "data"
        ]
        assert [m["name"] for m in overview["members"]] == ["Kari", "Ola"]  # Chair first
        assert overview["warnings"] == ["TOO_FEW_MEMBERS", "SAME_CLUB"]

        ola = overview["members"][1]["id"]
        response = await send_tournament_request(
            HTTPMethod.PUT,
            f"jury_members/{ola}",
            auth_context,
            json={"name": "Ola", "club_name": "Lyn"},
        )
        assert response == SUCCESS_RESPONSE
        await send_tournament_request(
            HTTPMethod.POST, "jury_members", auth_context, json={"name": "Per", "club_name": "Os"}
        )
        overview = (await send_tournament_request(HTTPMethod.GET, "jury_members", auth_context))[
            "data"
        ]
        assert overview["warnings"] == []

        # The district application lists them and has no jury warnings
        application = await send_tournament_request(
            HTTPMethod.GET, "district_application", auth_context
        )
        assert len(application["data"]["jury_members"]) == 3
        assert application["data"]["jury_warnings"] == []

        # A jury decision names its members, which must be from this jury
        member_ids = [m["id"] for m in overview["members"]]
        response = await send_tournament_request(
            HTTPMethod.POST,
            "jury_decisions",
            auth_context,
            json={"text": "Kampen spilles om", "member_ids": member_ids},
        )
        assert response == SUCCESS_RESPONSE
        response = await send_tournament_request(
            HTTPMethod.POST,
            "jury_decisions",
            auth_context,
            json={"text": "Feil", "member_ids": [999999]},
        )
        assert response == {"detail": "Could not find the jury member"}

        response = await send_tournament_request(
            HTTPMethod.DELETE, f"jury_members/{ola}", auth_context
        )
        assert response == SUCCESS_RESPONSE
        response = await send_tournament_request(
            HTTPMethod.DELETE, f"jury_members/{ola}", auth_context
        )
        assert response == {"detail": "Could not find the jury member"}
    finally:
        await clean_up(auth_context)
