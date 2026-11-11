import asyncio
from email.message import EmailMessage

import pytest

from bracket.database import database
from bracket.logic import notifications
from bracket.logic.notifications import (
    MAX_EMAILS_PER_ADDRESS_DAY,
    NotificationKind,
    Recipient,
    process_pending,
    queue,
    queue_registration_email,
)
from bracket.routes.notifications import bulk_sends, bulk_sends_per_user
from bracket.schema import notifications_sent, team_registrations, teams, tournament_details
from bracket.utils.email import set_email_sender
from bracket.utils.http import HTTPMethod
from bracket.utils.id_types import TeamId
from tests.integration_tests.api.cup_setup_test import delete_cup
from tests.integration_tests.api.score_links_test import set_up_playable_cup
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
from tests.integration_tests.models import AuthContext

CONTACTS = {"Brann": "brann@example.org", "Lyn": "lyn@example.org", "Fana": "fana@example.org"}


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []
        self.failing = False

    def send(self, message: EmailMessage) -> None:
        if self.failing:
            raise ConnectionError("SMTP server not reachable")
        self.sent.append(message)


async def add_contacts(auth_context: AuthContext, team_ids: dict[str, TeamId]) -> None:
    for name, email in CONTACTS.items():
        await database.execute(
            team_registrations.insert(),
            values={
                "team_id": team_ids[name],
                "tournament_id": auth_context.tournament.id,
                "contact_name": f"Kontakt {name}",
                "contact_email": email,
            },
        )


async def clean_up(auth_context: AuthContext) -> None:
    tournament_id = auth_context.tournament.id
    set_email_sender(None)
    bulk_sends.hits.clear()
    bulk_sends_per_user.hits.clear()
    await database.execute(
        notifications_sent.delete().where(notifications_sent.c.tournament_id == tournament_id)
    )
    await database.execute(
        tournament_details.delete().where(tournament_details.c.tournament_id == tournament_id)
    )
    await database.execute(
        "UPDATE tournaments SET announcement_text = NULL WHERE id = :id",
        values={"id": tournament_id},
    )
    await delete_cup(auth_context)


def assert_only_own_contact(messages: list[EmailMessage]) -> None:
    """Every email goes to one team and contains no other team's contact details."""
    for message in messages:
        others = set(CONTACTS.values()) - {message["To"]}
        body = message.get_content()
        assert not any(email in body for email in others)


@pytest.mark.asyncio(loop_scope="session")
async def test_announcement_and_schedule_emails(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    sender = FakeSender()
    try:
        team_ids = await set_up_playable_cup(auth_context)
        await add_contacts(auth_context, team_ids)
        set_email_sender(sender)
        await send_tournament_request(
            HTTPMethod.PUT,
            "details",
            auth_context,
            json={"contact_name": "Kari", "contact_email": "kari@example.org"},
        )

        # Announcement: once per text and team, only to teams with a contact
        response = await send_tournament_request(
            HTTPMethod.PUT,
            "announcement",
            auth_context,
            json={"announcement": {"text": "Lyn og torden: pause til 14:00"}},
        )
        assert response == SUCCESS_RESPONSE
        endpoint = "notifications/announcement"
        assert (await send_tournament_request(HTTPMethod.POST, endpoint, auth_context)) == {
            "data": 3
        }
        assert (await send_tournament_request(HTTPMethod.POST, endpoint, auth_context)) == {
            "data": 0
        }
        assert await process_pending(sender) == 3
        assert sorted(m["To"] for m in sender.sent) == sorted(CONTACTS.values())
        assert all("pause til 14:00" in m.get_content() for m in sender.sent)
        # Answers go to the organiser, whose contact is in the email
        assert {m["Reply-To"] for m in sender.sent} == {"kari@example.org"}
        assert all("Kari" in m.get_content() for m in sender.sent)
        assert_only_own_contact(sender.sent)
        sender.sent.clear()

        # Schedule: each team its own matches; again only after a change
        endpoint = "notifications/schedule"
        dry_run = await send_tournament_request(
            HTTPMethod.POST, f"{endpoint}?dry_run=true", auth_context
        )
        assert dry_run == {"data": {"teams_with_contact": 3, "teams_to_notify": 3}}
        await send_tournament_request(HTTPMethod.POST, endpoint, auth_context)
        assert await process_pending(sender) == 3
        brann_email = next(m for m in sender.sent if m["To"] == CONTACTS["Brann"])
        assert "Brann" in brann_email["Subject"]
        assert brann_email.get_content().count(" – ") == 2  # Brann plays two group matches
        assert_only_own_contact(sender.sent)
        sender.sent.clear()
        again = await send_tournament_request(HTTPMethod.POST, endpoint, auth_context)
        assert again == {"data": {"teams_with_contact": 3, "teams_to_notify": 0}}

        # A later start of one of Brann's matches: Brann and its opponent get a new notice
        await database.execute(
            """
            UPDATE matches SET start_time = start_time + interval '30 minutes'
            WHERE id = (
                SELECT m.id FROM matches m
                JOIN stage_item_inputs i ON i.id IN (m.stage_item_input1_id, m.stage_item_input2_id)
                WHERE i.team_id = :team_id ORDER BY m.id LIMIT 1
            )
            """,
            values={"team_id": team_ids["Brann"]},
        )
        changed = await send_tournament_request(
            HTTPMethod.POST, f"{endpoint}?dry_run=true", auth_context
        )
        # Brann, and its opponent if that team has a contact
        assert changed["data"]["teams_to_notify"] in (1, 2)

        overview = await send_tournament_request(HTTPMethod.GET, "notifications", auth_context)
        assert overview["data"]["email_enabled"] is True
        assert overview["data"]["sent"] == 6
        assert overview["data"]["language"] == "nb"
    finally:
        await clean_up(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_emails_without_smtp_and_retries(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    sender = FakeSender()
    try:
        team_ids = await set_up_playable_cup(auth_context)
        await add_contacts(auth_context, team_ids)

        # Not set up: nothing is queued, the organiser gets the addresses to write themselves
        await send_tournament_request(
            HTTPMethod.PUT, "announcement", auth_context, json={"announcement": {"text": "Hei"}}
        )
        response = await send_tournament_request(
            HTTPMethod.POST, "notifications/announcement", auth_context
        )
        assert response == {"detail": "Email is not set up on this server"}
        overview = (await send_tournament_request(HTTPMethod.GET, "notifications", auth_context))[
            "data"
        ]
        assert overview["email_enabled"] is False
        assert overview["contact_emails"] == sorted(CONTACTS.values())
        await queue_registration_email(tournament_id, team_ids["Brann"], None)
        overview = (await send_tournament_request(HTTPMethod.GET, "notifications", auth_context))[
            "data"
        ]
        assert (overview["pending"], overview["recent"]) == (0, [])

        # Failures are retried, then marked failed
        set_email_sender(sender)
        await send_tournament_request(
            HTTPMethod.PUT, "notification_settings", auth_context, json={"language": "en"}
        )
        await queue_registration_email(tournament_id, team_ids["Brann"], 2)
        sender.failing = True
        for _ in range(3):
            assert await process_pending(sender) == 0
        overview = (await send_tournament_request(HTTPMethod.GET, "notifications", auth_context))[
            "data"
        ]
        assert (overview["pending"], overview["failed"]) == (0, 1)
        assert overview["recent"][0]["error"] == "SMTP server not reachable"
        assert overview["recent"][0]["kind"] == "REGISTRATION"

        # Moving up from the waitlist: an email to that team
        sender.failing = False
        await database.execute(
            teams.update().where(teams.c.id == team_ids["Lyn"]),
            values={"registration_status": "WAITLIST"},
        )
        response = await send_tournament_request(
            HTTPMethod.PUT,
            f"registrations/{team_ids['Lyn']}",
            auth_context,
            json={
                "registration_status": "APPROVED",
                "contact_name": "Kontakt Lyn",
                "contact_email": CONTACTS["Lyn"],
                "contact_phone": None,
                "comment": None,
                "paid": False,
                "squad_reported": False,
            },
        )
        assert response == SUCCESS_RESPONSE
        assert await process_pending(sender) == 1
        assert len(sender.sent) == 1
        message = sender.sent[0]
        assert (message["To"], message["Subject"]) == (
            CONTACTS["Lyn"],
            f"{auth_context.tournament.name}: Lyn has a place",
        )
    finally:
        await clean_up(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_registration_email_is_no_spam_relay(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """The public form chooses the address: the email only has the organiser's text."""
    tournament_id = auth_context.tournament.id
    sender = FakeSender()
    try:
        team_ids = await set_up_playable_cup(auth_context)
        await add_contacts(auth_context, team_ids)
        set_email_sender(sender)
        await database.execute(
            teams.update().where(teams.c.id == team_ids["Brann"]),
            values={"name": "Buy cheap pills"},
        )
        await database.execute(
            team_registrations.update().where(team_registrations.c.team_id == team_ids["Brann"]),
            values={"contact_name": "Visit spam.example"},
        )
        await queue_registration_email(tournament_id, team_ids["Brann"], None)
        await queue_registration_email(tournament_id, team_ids["Brann"], 2)
        assert await process_pending(sender) == 2
        for message in sender.sent:
            text = message["Subject"] + message.get_content()
            assert "pills" not in text and "spam.example" not in text
            assert "G10" in text

        # At most 3 a day to the same address (also from other teams with that address)
        for name in ("Lyn", "Fana"):
            await database.execute(
                team_registrations.update().where(team_registrations.c.team_id == team_ids[name]),
                values={"contact_email": CONTACTS["Brann"]},
            )
            await queue_registration_email(tournament_id, team_ids[name], None)
        assert await process_pending(sender) == 1
    finally:
        await clean_up(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_poison_message_fails_without_blocking(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    sender = FakeSender()
    try:
        team_ids = await set_up_playable_cup(auth_context)
        rows = [
            ("poison", "x@example.org\r\nBcc: victim@example.org", "Hei"),
            ("good", "ok@example.org", "Hei\r\nBcc: victim@example.org"),
        ]
        for key, recipient, subject in rows:
            await database.execute(
                notifications_sent.insert(),
                values={
                    "tournament_id": tournament_id,
                    "team_id": team_ids["Brann"],
                    "kind": "ANNOUNCEMENT",
                    "dedupe_key": key,
                    "recipient": recipient,
                    "subject": subject,
                    "body": "Tekst",
                },
            )
        assert await process_pending(sender) == 1
        assert len(sender.sent) == 1
        message = sender.sent[0]
        assert message["To"] == "ok@example.org"
        assert "\n" not in message["Subject"] and message["Bcc"] is None
        status = await database.fetch_one(
            notifications_sent.select().where(notifications_sent.c.dedupe_key == "poison")
        )
        assert status is not None
        assert (status["status"], status["attempts"]) == ("FAILED", 1)
        assert await process_pending(sender) == 0
    finally:
        await clean_up(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_names_without_control_characters(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    body = {"name": "Brann\r\nBcc: x@example.org", "active": True, "player_ids": []}
    response = await send_tournament_request(HTTPMethod.POST, "teams", auth_context, json=body)
    assert "control characters" in str(response)
    response = await send_tournament_request(
        HTTPMethod.POST,
        "teams_multi",
        auth_context,
        json={"names": "Brann\x1b[31m\nLyn", "active": True},
    )
    assert response == {"detail": "Names may not contain control characters"}
    response = await send_tournament_request(
        HTTPMethod.POST, "categories", auth_context, json={"name": "G10\nBcc: x"}
    )
    assert "control characters" in str(response)


@pytest.mark.asyncio(loop_scope="session")
async def test_registration_email_limit_holds_under_concurrency(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """Six confirmations at once to one address: exactly three are queued."""
    tournament_id = auth_context.tournament.id
    sender = FakeSender()
    try:
        team_ids = await set_up_playable_cup(auth_context)
        await add_contacts(auth_context, team_ids)
        await database.execute(
            team_registrations.update().where(team_registrations.c.tournament_id == tournament_id),
            values={"contact_email": "same@example.org"},
        )
        set_email_sender(sender)
        await asyncio.gather(
            *(
                queue_registration_email(tournament_id, team_ids[name], place)
                for name in CONTACTS
                for place in (None, 1)
            )
        )
        assert await process_pending(sender) == 3
    finally:
        await clean_up(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_address_gets_limited_emails_per_day(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    """Whatever the kind, an address gets at most MAX_EMAILS_PER_ADDRESS_DAY a day per cup."""
    tournament_id = auth_context.tournament.id
    try:
        team_ids = await set_up_playable_cup(auth_context)
        recipient = Recipient(
            team_id=team_ids["Brann"],
            team_name="Brann",
            category_name=None,
            contact_name="Kontakt",
            email="flood@example.org",
        )
        results = await asyncio.gather(
            *(
                queue(
                    tournament_id,
                    recipient,
                    NotificationKind.ANNOUNCEMENT,
                    f"test:{index}",
                    "Subject",
                    "Body",
                    None,
                )
                for index in range(MAX_EMAILS_PER_ADDRESS_DAY + 5)
            )
        )
        assert sum(results) == MAX_EMAILS_PER_ADDRESS_DAY
        # The rest is visible to the organiser as failed, and never sent
        failed = await database.fetch_val(
            """
            SELECT count(*) FROM notifications_sent
            WHERE tournament_id = :id AND status = 'FAILED'
            """,
            values={"id": tournament_id},
        )
        assert failed == 5
    finally:
        await clean_up(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_address_global_limit(
    startup_and_shutdown_uvicorn_server: None,
    auth_context: AuthContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The global limit over all cups also holds (lowered here to test it with one cup)."""
    monkeypatch.setattr(notifications, "MAX_EMAILS_PER_ADDRESS_DAY_GLOBAL", 3)
    tournament_id = auth_context.tournament.id
    try:
        team_ids = await set_up_playable_cup(auth_context)
        recipient = Recipient(
            team_id=team_ids["Brann"],
            team_name="Brann",
            category_name=None,
            contact_name="Kontakt",
            email="global@example.org",
        )
        results = await asyncio.gather(
            *(
                queue(
                    tournament_id,
                    recipient,
                    NotificationKind.ANNOUNCEMENT,
                    f"global:{index}",
                    "Subject",
                    "Body",
                    None,
                )
                for index in range(6)
            )
        )
        assert sum(results) == 3
    finally:
        await clean_up(auth_context)
