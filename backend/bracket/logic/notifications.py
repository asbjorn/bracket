"""
Email to the contact person of each team (from the registration): announcements, schedule
changes, registration confirmations and moving up from the waitlist.

Every email goes to one team's own contact and only mentions that team; other teams' contact
details are never included. Emails are queued in `notifications_sent` and sent in the
background (`send_pending_notifications`), a few at a time. A `dedupe_key` per message makes
sure the same message is never queued twice, also when a request is retried.
"""

import hashlib
import re
from dataclasses import dataclass
from email.message import EmailMessage
from enum import StrEnum

from heliclockter import datetime_utc, timedelta
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from bracket.database import database
from bracket.logic.district_application import get_details
from bracket.logic.walkovers import team_of
from bracket.models.db.district_application import TournamentDetails
from bracket.models.db.team import PARTICIPATING_STATUSES, RegistrationStatus
from bracket.sql.categories import get_all_categories_in_tournament
from bracket.sql.courts import get_all_courts_in_tournament
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.tournaments import sql_get_tournament
from bracket.utils.cup_time import CUP_TIMEZONE
from bracket.utils.email import EmailSender, get_email_sender, sender_address
from bracket.utils.id_types import TeamId, TournamentId
from bracket.utils.logging import logger
from bracket.utils.text import strip_control_characters

SEND_BATCH_SIZE = 20  # Per run of the cronjob (every 15 seconds): at most 80 emails a minute
MAX_ATTEMPTS = 3
# Sign-up confirmations (the public form can trigger them): per address a day, per cup an hour
MAX_REGISTRATION_EMAILS_PER_ADDRESS = 3
MAX_REGISTRATION_EMAILS_HOUR = 60
# Any kind of email to one address a day: per tournament, and (higher) over all tournaments of
# the same club (organiser). Counted only within the organiser's own tournaments, so another
# organiser can neither use up these limits nor learn anything from them; an address can't be
# flooded by creating many tournaments.
MAX_EMAILS_PER_ADDRESS_DAY = 20
MAX_EMAILS_PER_ADDRESS_DAY_CLUB = 100
# A ceiling over the whole server as a last line of defence against flooding one address via
# many clubs. Reaching it needs several clubs and accounts (bulk sends are limited per user).
# All limits give the same generic error, so it reveals nothing about other organisers.
MAX_EMAILS_PER_ADDRESS_DAY_SERVER = 300
# A plain address, nothing that could add headers or recipients
PLAIN_ADDRESS = re.compile(r"^[^\s@<>,;:\"()\[\]\\]+@[^\s@<>,;:\"()\[\]\\]+$")
STALE_SENDING = timedelta(minutes=10)


class EmailLanguage(StrEnum):
    NB = "nb"
    EN = "en"


class NotificationKind(StrEnum):
    ANNOUNCEMENT = "ANNOUNCEMENT"
    SCHEDULE = "SCHEDULE"
    REGISTRATION = "REGISTRATION"
    PROMOTION = "PROMOTION"


TEXTS: dict[EmailLanguage, dict[str, str]] = {
    EmailLanguage.NB: {
        "greeting": "Hei {name},",
        "announcement_subject": "{tournament}: melding fra arrangøren",
        "schedule_subject": "{tournament}: kampoppsett for {team}",
        "schedule_intro": "Her er de neste kampene for {team}:",
        "schedule_note": "Tidene kan endres. Følg med på cupens nettside for siste oppdatering.",
        "greeting_plain": "Hei,",
        "registered_subject": "{tournament}: påmelding mottatt",
        "registered": "Takk! Påmeldingen til klassen {category} er registrert.",
        "waitlist_subject": "{tournament}: påmelding på venteliste",
        "waitlist": "Påmeldingen til klassen {category} står på venteliste, plass {place}. "
        "Vi gir beskjed hvis det blir ledig plass.",
        "promotion_subject": "{tournament}: {team} har fått plass",
        "promotion": "Godt nytt! {team} har fått plass i klassen {category}.",
        "organiser": "Spørsmål? Kontakt arrangøren:",
        "footer": "Du får denne e-posten fordi du er kontaktperson for et lag i {tournament}.",
        "weekdays": "man.,tir.,ons.,tor.,fre.,lør.,søn.",
        "at": "kl.",
    },
    EmailLanguage.EN: {
        "greeting": "Hi {name},",
        "announcement_subject": "{tournament}: message from the organiser",
        "schedule_subject": "{tournament}: schedule for {team}",
        "schedule_intro": "These are the next matches of {team}:",
        "schedule_note": "Times may change. See the cup's website for the latest schedule.",
        "greeting_plain": "Hello,",
        "registered_subject": "{tournament}: registration received",
        "registered": "Thank you! The registration for the class {category} is received.",
        "waitlist_subject": "{tournament}: registration on the waitlist",
        "waitlist": "The registration for the class {category} is on the waitlist, place "
        "{place}. We'll let you know when a place becomes available.",
        "promotion_subject": "{tournament}: {team} has a place",
        "promotion": "Good news! {team} now has a place in the class {category}.",
        "organiser": "Questions? Contact the organiser:",
        "footer": "You get this email as the contact person of a team in {tournament}.",
        "weekdays": "Mon,Tue,Wed,Thu,Fri,Sat,Sun",
        "at": "at",
    },
}


@dataclass(frozen=True)
class Recipient:
    team_id: TeamId
    team_name: str
    category_name: str | None
    contact_name: str
    email: str


class NotificationOut(BaseModel):
    created: datetime_utc
    kind: NotificationKind
    team_name: str | None
    recipient: str
    status: str
    error: str | None


class NotificationStatus(BaseModel):
    email_enabled: bool
    language: EmailLanguage
    pending: int
    sent: int
    failed: int
    recent: list[NotificationOut]
    # For writing an email yourself (BCC) when email isn't set up on the server
    contact_emails: list[str]


class NotificationSettingsBody(BaseModel):
    language: EmailLanguage


class ScheduleNoticeResult(BaseModel):
    teams_with_contact: int
    # Teams whose schedule changed since their last notice (or that never got one)
    teams_to_notify: int


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:24]


async def get_language(tournament_id: TournamentId) -> EmailLanguage:
    value = await database.fetch_val(
        "SELECT email_language FROM tournament_details WHERE tournament_id = :tournament_id",
        values={"tournament_id": tournament_id},
    )
    return (
        EmailLanguage(value)
        if value in {lang.value for lang in EmailLanguage}
        else EmailLanguage.NB
    )


async def set_language(tournament_id: TournamentId, language: EmailLanguage) -> None:
    await database.execute(
        """
        INSERT INTO tournament_details (tournament_id, email_language)
        VALUES (:tournament_id, :language)
        ON CONFLICT (tournament_id) DO UPDATE SET email_language = excluded.email_language
        """,
        values={"tournament_id": tournament_id, "language": language.value},
    )


async def get_recipients(
    tournament_id: TournamentId, team_id: TeamId | None = None, *, only_participating: bool = True
) -> list[Recipient]:
    """Teams with a contact email (from the registration), by default only those taking part."""
    statuses = sorted(
        status.value
        for status in (PARTICIPATING_STATUSES if only_participating else RegistrationStatus)
    )
    rows = await database.fetch_all(
        """
        SELECT teams.id, teams.name, categories.name AS category_name, r.contact_name,
            r.contact_email
        FROM teams
        JOIN team_registrations r ON r.team_id = teams.id
        LEFT JOIN categories ON categories.id = teams.category_id
        WHERE teams.tournament_id = :tournament_id
        AND r.contact_email IS NOT NULL AND r.contact_email != ''
        AND teams.registration_status = any(:statuses)
        AND (CAST(:team_id AS BIGINT) IS NULL OR teams.id = :team_id)
        ORDER BY teams.id
        """,
        values={"tournament_id": tournament_id, "statuses": statuses, "team_id": team_id},
    )
    return [
        Recipient(
            team_id=TeamId(row["id"]),
            team_name=row["name"],
            category_name=row["category_name"],
            contact_name=row["contact_name"] or "",
            email=row["contact_email"],
        )
        for row in rows
    ]


def organiser_block(texts: dict[str, str], details: TournamentDetails) -> list[str]:
    contact = [
        part
        for part in (details.contact_name, details.contact_phone, details.contact_email)
        if part
    ]
    return ["", texts["organiser"], ", ".join(contact)] if contact else []


async def compose(
    tournament_id: TournamentId,
    recipient: Recipient,
    subject_key: str,
    lines: list[str],
    *,
    personal: bool = True,
) -> tuple[str, str, str | None]:
    """
    Subject, body and reply-to address of an email to one team's contact. Not `personal`:
    without the names the contact typed in (for emails caused by the public sign-up form).
    """
    tournament = await sql_get_tournament(tournament_id)
    details = await get_details(tournament_id)
    texts = TEXTS[await get_language(tournament_id)]
    subject = texts[subject_key].format(tournament=tournament.name, team=recipient.team_name)
    greeting = (
        texts["greeting"].format(name=recipient.contact_name or recipient.team_name)
        if personal
        else texts["greeting_plain"]
    )
    body = "\n".join(
        [
            greeting,
            "",
            *lines,
            *organiser_block(texts, details),
            "",
            "--",
            texts["footer"].format(tournament=tournament.name),
        ]
    )
    return subject, body + "\n", details.contact_email or None


async def queue(  # pylint: disable=too-many-arguments
    tournament_id: TournamentId,
    recipient: Recipient,
    kind: NotificationKind,
    dedupe_key: str,
    subject: str,
    body: str,
    reply_to: str | None,
) -> bool:
    """
    Queues an email; `False` if this message (`dedupe_key`) was queued before, or the address
    already got `MAX_EMAILS_PER_ADDRESS_DAY` emails from this tournament, or
    `MAX_EMAILS_PER_ADDRESS_DAY_CLUB` from all tournaments of its club, in the last day (under a
    lock). An email over a limit is logged as failed for the organiser to see.
    """
    async with database.transaction():
        # One lock per address (not per tournament), so both counts hold under concurrency
        await database.execute(
            "SELECT pg_advisory_xact_lock(hashtext(:key))",
            values={"key": f"email-address:{recipient.email.lower()}"},
        )
        counts = await database.fetch_one(
            """
            SELECT
                count(*) FILTER (WHERE n.tournament_id = :tournament_id) AS this_tournament,
                count(*) FILTER (
                    WHERE t.club_id = (SELECT club_id FROM tournaments WHERE id = :tournament_id)
                ) AS club_tournaments,
                count(*) AS all_tournaments
            FROM notifications_sent n
            JOIN tournaments t ON t.id = n.tournament_id
            WHERE lower(n.recipient) = lower(:email)
            AND n.status <> 'FAILED'
            AND n.created > now() - interval '1 day'
            """,
            values={"tournament_id": tournament_id, "email": recipient.email},
        )
        assert counts is not None
        over_limit = (
            int(counts["this_tournament"]) >= MAX_EMAILS_PER_ADDRESS_DAY
            or int(counts["club_tournaments"]) >= MAX_EMAILS_PER_ADDRESS_DAY_CLUB
            or int(counts["all_tournaments"]) >= MAX_EMAILS_PER_ADDRESS_DAY_SERVER
        )
        inserted = await insert_notification(
            tournament_id, recipient, kind, dedupe_key, subject, body, reply_to
        )
        if inserted is not None and over_limit:
            logger.warning(f"Not emailing team {recipient.team_id}: daily limit for the address")
            await database.execute(
                """
                UPDATE notifications_sent
                SET status = 'FAILED', attempts = :attempts, error = :error
                WHERE id = :id
                """,
                values={
                    "id": inserted,
                    "attempts": MAX_ATTEMPTS,
                    "error": "Daily email limit reached",
                },
            )
        return inserted is not None and not over_limit


async def insert_notification(  # pylint: disable=too-many-arguments
    tournament_id: TournamentId,
    recipient: Recipient,
    kind: NotificationKind,
    dedupe_key: str,
    subject: str,
    body: str,
    reply_to: str | None,
) -> int | None:
    """The id of the new row, or `None` if this message (`dedupe_key`) was queued before."""
    inserted = await database.fetch_val(
        """
        INSERT INTO notifications_sent (
            tournament_id, team_id, kind, dedupe_key, recipient, reply_to, subject, body
        )
        VALUES (
            :tournament_id, :team_id, :kind, :dedupe_key, :recipient, :reply_to, :subject, :body
        )
        ON CONFLICT (tournament_id, dedupe_key) DO NOTHING
        RETURNING id
        """,
        values={
            "tournament_id": tournament_id,
            "team_id": recipient.team_id,
            "kind": kind.value,
            "dedupe_key": dedupe_key,
            "recipient": recipient.email,
            "reply_to": reply_to,
            "subject": subject,
            "body": body,
        },
    )
    return None if inserted is None else int(inserted)


async def queue_announcement(tournament_id: TournamentId, text: str) -> int:
    """The announcement to every participating team; the same text is never sent twice."""
    queued = 0
    for recipient in await get_recipients(tournament_id):
        subject, body, reply_to = await compose(
            tournament_id, recipient, "announcement_subject", [text.strip()]
        )
        key = f"announcement:{recipient.team_id}:{digest(text.strip())}"
        if await queue(
            tournament_id, recipient, NotificationKind.ANNOUNCEMENT, key, subject, body, reply_to
        ):
            queued += 1
    return queued


def format_time(moment: datetime_utc, texts: dict[str, str]) -> str:
    local = moment.astimezone(CUP_TIMEZONE)
    weekday = texts["weekdays"].split(",")[local.weekday()]
    return f"{weekday} {local:%d.%m} {texts['at']} {local:%H:%M}"


async def schedule_lines(
    tournament_id: TournamentId, texts: dict[str, str]
) -> dict[TeamId, list[str]]:
    """Per team: its planned matches that aren't played yet, in order of time."""
    courts = {court.id: court.name for court in await get_all_courts_in_tournament(tournament_id)}
    categories = {c.id: c.name for c in await get_all_categories_in_tournament(tournament_id)}
    planned: dict[TeamId, list[tuple[datetime_utc, str]]] = {}
    for stage in await get_full_tournament_details(tournament_id):
        category = categories.get(stage.category_id) if stage.category_id is not None else None
        for item in stage.stage_items:
            for round_ in item.rounds:
                for match in round_.matches:
                    if match.played or match.start_time is None:
                        continue
                    team1_id, team1_name = team_of(match.stage_item_input1)
                    team2_id, team2_name = team_of(match.stage_item_input2)
                    court = courts.get(match.court_id) if match.court_id is not None else None
                    line = (
                        f"- {format_time(match.start_time, texts)}"
                        f"{f', {court}' if court else ''}: "
                        f"{team1_name or '?'} – {team2_name or '?'}"
                        f"{f' ({category})' if category else ''}"
                    )
                    for team_id in (team1_id, team2_id):
                        if team_id is not None:
                            planned.setdefault(team_id, []).append((match.start_time, line))
    return {
        team_id: [line for _, line in sorted(matches, key=lambda pair: pair[0])]
        for team_id, matches in planned.items()
    }


async def last_schedule_digest(tournament_id: TournamentId, team_id: TeamId) -> tuple[int, str]:
    """
    The id of the last schedule notice to this team, and the digest of the last one that
    didn't fail (0, "" if none). A failed notice doesn't count as sent, so the same schedule
    is tried again; its id still goes into the new key, so the retry isn't a duplicate.
    """
    row = await database.fetch_one(
        """
        SELECT
            max(id) AS last_id,
            (array_agg(dedupe_key ORDER BY id DESC) FILTER (WHERE status <> 'FAILED'))[1]
                AS last_key
        FROM notifications_sent
        WHERE tournament_id = :tournament_id AND team_id = :team_id AND kind = 'SCHEDULE'
        """,
        values={"tournament_id": tournament_id, "team_id": team_id},
    )
    if row is None or row["last_id"] is None:
        return 0, ""
    last_key = row["last_key"]
    return int(row["last_id"]), "" if last_key is None else str(last_key).rsplit(":", 1)[-1]


async def queue_schedule_notices(
    tournament_id: TournamentId, *, dry_run: bool
) -> ScheduleNoticeResult:
    """
    Each team's next matches, only to teams whose schedule changed since their last notice.
    With `dry_run`, only counts them.
    """
    texts = TEXTS[await get_language(tournament_id)]
    lines_per_team = await schedule_lines(tournament_id, texts)
    recipients = [r for r in await get_recipients(tournament_id) if r.team_id in lines_per_team]
    to_notify = 0
    for recipient in recipients:
        lines = lines_per_team[recipient.team_id]
        schedule_digest = digest("\n".join(lines))
        last_id, last_digest = await last_schedule_digest(tournament_id, recipient.team_id)
        if schedule_digest == last_digest:
            continue
        to_notify += 1
        if dry_run:
            continue
        subject, body, reply_to = await compose(
            tournament_id,
            recipient,
            "schedule_subject",
            [
                texts["schedule_intro"].format(team=recipient.team_name),
                *lines,
                "",
                texts["schedule_note"],
            ],
        )
        key = f"schedule:{recipient.team_id}:{last_id}:{schedule_digest}"
        await queue(
            tournament_id, recipient, NotificationKind.SCHEDULE, key, subject, body, reply_to
        )
    return ScheduleNoticeResult(teams_with_contact=len(recipients), teams_to_notify=to_notify)


async def queue_registration_email(
    tournament_id: TournamentId, team_id: TeamId, waitlist_place: int | None
) -> None:
    """
    Confirms a sign-up: registered, or on the waitlist (with the place).

    Anyone can sign up with any address, so this email must not be usable to send text of
    the sender's choice: it only contains what the organiser wrote (cup and class names, the
    organiser's contact), never the team name, contact name or comment from the form. And
    an address gets at most a few of them a day, a cup at most `MAX_REGISTRATION_EMAILS_HOUR`.
    """
    if get_email_sender() is None:
        return
    recipients = await get_recipients(tournament_id, team_id, only_participating=False)
    if len(recipients) < 1:
        return
    [recipient] = recipients
    texts = TEXTS[await get_language(tournament_id)]
    category = recipient.category_name or ""
    if waitlist_place is None:
        subject_key, line = "registered_subject", texts["registered"].format(category=category)
    else:
        subject_key = "waitlist_subject"
        line = texts["waitlist"].format(category=category, place=waitlist_place)
    subject, body, reply_to = await compose(
        tournament_id, recipient, subject_key, [line], personal=False
    )
    key = f"registration:{team_id}:{'waitlist' if waitlist_place is not None else 'registered'}"
    async with database.transaction():
        # Check and queue at once: concurrent sign-ups can't pass the limits together.
        # Always the tournament first, then the address, so two locks can't deadlock.
        await database.execute(
            "SELECT pg_advisory_xact_lock(hashtext(:key))",
            values={"key": f"registration-email:tournament:{tournament_id}"},
        )
        await database.execute(
            "SELECT pg_advisory_xact_lock(hashtext(:key))",
            values={"key": f"registration-email:address:{recipient.email.lower()}"},
        )
        if await too_many_registration_emails(tournament_id, recipient.email):
            logger.warning(f"Not confirming registration of team {team_id}: too many emails")
            return
        await queue(
            tournament_id, recipient, NotificationKind.REGISTRATION, key, subject, body, reply_to
        )


async def too_many_registration_emails(tournament_id: TournamentId, email: str) -> bool:
    counts = await database.fetch_one(
        """
        SELECT
            count(*) FILTER (
                WHERE lower(recipient) = lower(:email) AND created > now() - interval '1 day'
            ) AS per_address,
            count(*) FILTER (
                WHERE tournament_id = :tournament_id AND created > now() - interval '1 hour'
            ) AS per_tournament
        FROM notifications_sent
        WHERE kind = 'REGISTRATION'
        AND (lower(recipient) = lower(:email) OR tournament_id = :tournament_id)
        """,
        values={"email": email, "tournament_id": tournament_id},
    )
    assert counts is not None
    return (
        int(counts["per_address"]) >= MAX_REGISTRATION_EMAILS_PER_ADDRESS
        or int(counts["per_tournament"]) >= MAX_REGISTRATION_EMAILS_HOUR
    )


async def queue_promotion_email(tournament_id: TournamentId, team_id: TeamId) -> None:
    """The team moved up from the waitlist and takes part."""
    if get_email_sender() is None:
        return
    recipients = await get_recipients(tournament_id, team_id)
    if len(recipients) < 1:
        return
    [recipient] = recipients
    texts = TEXTS[await get_language(tournament_id)]
    line = texts["promotion"].format(
        team=recipient.team_name, category=recipient.category_name or ""
    )
    subject, body, reply_to = await compose(tournament_id, recipient, "promotion_subject", [line])
    await queue(
        tournament_id,
        recipient,
        NotificationKind.PROMOTION,
        f"promoted:{team_id}",
        subject,
        body,
        reply_to,
    )


def build_message(recipient: str, reply_to: str | None, subject: str, body: str) -> EmailMessage:
    """Headers get no control characters; addresses must be plain addresses."""
    for address in (recipient, reply_to):
        if address is not None and not PLAIN_ADDRESS.match(address):
            raise ValueError("Not a valid email address")
    message = EmailMessage()
    message["From"] = sender_address()
    message["To"] = recipient
    if reply_to:
        message["Reply-To"] = reply_to
    message["Subject"] = strip_control_characters(subject)[:200]
    message.set_content(body)
    return message


async def mark_failed(notification_id: int, error: Exception, *, final: bool) -> None:
    await database.execute(
        "UPDATE notifications_sent SET status = :status, error = :error WHERE id = :id",
        values={
            "id": notification_id,
            "status": "FAILED" if final else "PENDING",
            "error": str(error)[:500],
        },
    )


async def process_pending(sender: EmailSender, limit: int = SEND_BATCH_SIZE) -> int:
    """Sends up to `limit` queued emails; failures are retried up to `MAX_ATTEMPTS` times."""
    # Emails left "sending" by a stopped process are sent again
    await database.execute(
        """
        UPDATE notifications_sent SET status = 'PENDING'
        WHERE status = 'SENDING' AND claimed_at < :stale
        """,
        values={"stale": datetime_utc.now() - STALE_SENDING},
    )
    rows = await database.fetch_all(
        """
        UPDATE notifications_sent
        SET status = 'SENDING', attempts = attempts + 1, claimed_at = now()
        WHERE id IN (
            SELECT id FROM notifications_sent
            WHERE status = 'PENDING' AND attempts < :max_attempts
            ORDER BY id LIMIT :limit FOR UPDATE SKIP LOCKED
        )
        RETURNING id, recipient, reply_to, subject, body, attempts
        """,
        values={"limit": limit, "max_attempts": MAX_ATTEMPTS},
    )
    sent = 0
    for row in rows:
        try:
            message = build_message(row["recipient"], row["reply_to"], row["subject"], row["body"])
        except ValueError as error:
            # Can't ever be sent: don't try again
            await mark_failed(row["id"], error, final=True)
            continue
        try:
            await run_in_threadpool(sender.send, message)
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.warning(f"Could not send notification {row['id']}: {error}")
            await mark_failed(row["id"], error, final=row["attempts"] >= MAX_ATTEMPTS)
            continue
        await database.execute(
            """
            UPDATE notifications_sent SET status = 'SENT', sent_at = now(), error = NULL
            WHERE id = :id
            """,
            values={"id": row["id"]},
        )
        sent += 1
    return sent


async def send_pending_notifications() -> None:
    """Cronjob: sends queued emails when email is set up."""
    sender = get_email_sender()
    if sender is not None:
        await process_pending(sender)


async def get_notification_status(tournament_id: TournamentId) -> NotificationStatus:
    counts = {
        row["status"]: int(row["count"])
        for row in await database.fetch_all(
            """
            SELECT status, count(*) AS count FROM notifications_sent
            WHERE tournament_id = :tournament_id GROUP BY status
            """,
            values={"tournament_id": tournament_id},
        )
    }
    recent = await database.fetch_all(
        """
        SELECT n.created, n.kind, teams.name AS team_name, n.recipient, n.status, n.error
        FROM notifications_sent n
        LEFT JOIN teams ON teams.id = n.team_id
        WHERE n.tournament_id = :tournament_id
        ORDER BY n.id DESC LIMIT 50
        """,
        values={"tournament_id": tournament_id},
    )
    recipients = await get_recipients(tournament_id)
    return NotificationStatus(
        email_enabled=get_email_sender() is not None,
        language=await get_language(tournament_id),
        pending=counts.get("PENDING", 0) + counts.get("SENDING", 0),
        sent=counts.get("SENT", 0),
        failed=counts.get("FAILED", 0),
        recent=[NotificationOut.model_validate(dict(row._mapping)) for row in recent],
        contact_emails=sorted({recipient.email for recipient in recipients}),
    )
