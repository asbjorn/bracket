"""
Registration of teams: public sign-up per class (until the deadline, then a waitlist when the
class is full) and the organiser's overview with contact details, payment and export.

Contact details live in `team_registrations`, which is only read by the organiser's endpoints.
"""

from fastapi import HTTPException
from heliclockter import datetime_utc
from starlette import status

from bracket.database import database
from bracket.logic.notifications import queue_promotion_email, queue_registration_email
from bracket.logic.participating_clubs import find_or_create_club
from bracket.logic.subscriptions import check_requirement
from bracket.models.db.category import Category
from bracket.models.db.registration import (
    EntryFeeBody,
    PublicRegistrationBody,
    PublicRegistrationClass,
    PublicRegistrationResult,
    Registration,
    RegistrationSettingsBody,
    RegistrationTeam,
    RegistrationUpdateBody,
    TeamRegistrationResult,
)
from bracket.models.db.team import PARTICIPATING_STATUSES, RegistrationStatus
from bracket.models.db.tournament import TournamentStatus
from bracket.models.db.user import UserPublic
from bracket.sql.categories import get_all_categories_in_tournament
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.tournaments import sql_get_tournament
from bracket.sql.users import get_tournament_owner
from bracket.utils.csv_export import to_csv
from bracket.utils.id_types import CategoryId, ParticipatingClubId, TeamId, TournamentId

# Teams (any status, also rejected) per tournament: a cap on what the public form can create
MAX_TEAMS_PER_TOURNAMENT = 500

PARTICIPATING = tuple(sorted(status.value for status in PARTICIPATING_STATUSES))


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail)


def is_open(category: Category, now: datetime_utc) -> bool:
    return category.registration_open and (
        category.registration_deadline is None or now < category.registration_deadline
    )


async def participating_count(category_id: CategoryId) -> int:
    count = await database.fetch_val(
        """
        SELECT count(*) FROM teams
        WHERE category_id = :category_id AND registration_status = any(:statuses)
        """,
        values={"category_id": category_id, "statuses": list(PARTICIPATING)},
    )
    return int(count)


async def get_open_classes(
    tournament_id: TournamentId, now: datetime_utc
) -> list[PublicRegistrationClass]:
    if (await sql_get_tournament(tournament_id)).status is TournamentStatus.ARCHIVED:
        return []
    classes = []
    for category in await get_all_categories_in_tournament(tournament_id):
        if not is_open(category, now):
            continue
        spots_left = (
            None
            if category.max_teams is None
            else max(0, category.max_teams - await participating_count(category.id))
        )
        classes.append(
            PublicRegistrationClass(
                id=category.id,
                name=category.name,
                age=category.age,
                registration_deadline=category.registration_deadline,
                entry_fee=category.entry_fee,
                spots_left=spots_left,
            )
        )
    return classes


async def waitlist_place(category_id: CategoryId, team_id: TeamId) -> int | None:
    """Place on the waitlist (1 = first to move up), in order of registration."""
    rows = await database.fetch_all(
        """
        SELECT teams.id
        FROM teams
        LEFT JOIN team_registrations r ON r.team_id = teams.id
        WHERE teams.category_id = :category_id AND teams.registration_status = 'WAITLIST'
        ORDER BY r.registered_at NULLS LAST, teams.id
        """,
        values={"category_id": category_id},
    )
    ids = [row._mapping["id"] for row in rows]
    return ids.index(team_id) + 1 if team_id in ids else None


async def register_team(
    tournament_id: TournamentId, body: PublicRegistrationBody, now: datetime_utc
) -> PublicRegistrationResult:
    """Signs up the teams of the form (one, or several of a club), all or none."""
    results: list[TeamRegistrationResult] = []
    team_ids: list[TeamId] = []
    async with database.transaction():
        # One sign-up at a time per tournament (count and insert together), so two teams can't
        # take the last spot or pass the team limit. The tournament first, then the class.
        tournament = await database.fetch_one(
            "SELECT status FROM tournaments WHERE id = :id FOR UPDATE", values={"id": tournament_id}
        )
        if tournament is None or tournament._mapping["status"] == TournamentStatus.ARCHIVED.value:
            raise bad_request("Registration for this cup is closed")
        # The same limits as when the organiser adds teams: the subscription of the owner
        owner = await get_tournament_owner(tournament_id)
        if owner is None:
            raise bad_request("Registration for this cup is closed")
        # The free-text club from the form: the cup's club with that name, or a new one
        club_id = (
            await find_or_create_club(tournament_id, body.club_name) if body.club_name else None
        )
        for team in body.teams:
            team_id, result = await register_one_team(
                tournament_id, team, body, club_id, owner, now
            )
            team_ids.append(team_id)
            results.append(result)

    # One confirmation for the whole sign-up, however many teams it has
    await queue_registration_email(
        tournament_id,
        [
            (team_id, result.waitlist_place)
            for team_id, result in zip(team_ids, results, strict=True)
        ],
    )
    first = results[0]
    return PublicRegistrationResult(
        team_name=first.team_name,
        registration_status=first.registration_status,
        waitlist_place=first.waitlist_place,
        teams=results,
    )


async def register_one_team(  # pylint: disable=too-many-arguments
    tournament_id: TournamentId,
    team: RegistrationTeam,
    body: PublicRegistrationBody,
    club_id: ParticipatingClubId | None,
    owner: UserPublic,
    now: datetime_utc,
) -> tuple[TeamId, TeamRegistrationResult]:
    """One team of a sign-up, inside its transaction (the tournament row is locked)."""
    row = await database.fetch_one(
        "SELECT * FROM categories WHERE id = :id AND tournament_id = :tournament_id FOR UPDATE",
        values={"id": team.category_id, "tournament_id": tournament_id},
    )
    if row is None:
        raise bad_request("This class doesn't exist")
    category = Category.model_validate(dict(row._mapping))
    if not is_open(category, now):
        raise bad_request("Registration for this class is closed")
    # The waitlist follows the order of the locks, not of the requests
    registered_at = datetime_utc.now()

    team_count = int(
        await database.fetch_val(
            "SELECT count(*) FROM teams WHERE tournament_id = :tournament_id",
            values={"tournament_id": tournament_id},
        )
    )
    if team_count >= MAX_TEAMS_PER_TOURNAMENT:
        raise bad_request("Too many teams are registered, please contact the organiser")
    check_requirement([None] * team_count, owner, "max_teams")

    duplicate = await database.fetch_val(
        """
        SELECT count(*) FROM teams
        WHERE category_id = :category_id AND lower(name) = lower(:name)
        AND registration_status != 'REJECTED'
        """,
        values={"category_id": category.id, "name": team.team_name},
    )
    if int(duplicate) > 0:
        raise bad_request("A team with this name is already registered in this class")

    full = (
        category.max_teams is not None
        and await participating_count(category.id) >= category.max_teams
    )
    registration_status = RegistrationStatus.WAITLIST if full else RegistrationStatus.REGISTERED
    team_id = TeamId(
        await database.fetch_val(
            """
            INSERT INTO teams (
                name, created, tournament_id, active, elo_score, swiss_score, wins, draws,
                losses, category_id, club_id, registration_status, squad_size
            )
            VALUES (
                :name, :now, :tournament_id, true, 1200, 0, 0, 0, 0, :category_id, :club_id,
                :registration_status, :squad_size
            )
            RETURNING id
            """,
            values={
                "name": team.team_name,
                "now": registered_at,
                "tournament_id": tournament_id,
                "category_id": category.id,
                "club_id": club_id,
                "registration_status": registration_status.value,
                "squad_size": team.squad_size,
            },
        )
    )
    await database.execute(
        """
        INSERT INTO team_registrations (
            team_id, tournament_id, contact_name, contact_email, contact_phone, comment,
            registered_at
        )
        VALUES (
            :team_id, :tournament_id, :contact_name, :contact_email, :contact_phone,
            :comment, :now
        )
        """,
        values={
            "team_id": team_id,
            "tournament_id": tournament_id,
            "contact_name": body.contact_name,
            "contact_email": str(body.contact_email),
            "contact_phone": body.contact_phone,
            "comment": body.comment or None,
            "now": registered_at,
        },
    )
    place = await waitlist_place(category.id, team_id) if full else None
    return team_id, TeamRegistrationResult(
        team_name=team.team_name,
        category_id=category.id,
        registration_status=registration_status,
        waitlist_place=place,
    )


async def get_registrations(tournament_id: TournamentId) -> list[Registration]:
    rows = await database.fetch_all(
        """
        SELECT
            teams.id AS team_id, teams.name AS team_name, clubs.name AS club_name,
            teams.category_id,
            teams.registration_status, teams.withdrawn,
            r.contact_name, r.contact_email, r.contact_phone, r.comment, r.registered_at,
            coalesce(r.paid, false) AS paid, coalesce(r.squad_reported, false) AS squad_reported
        FROM teams
        LEFT JOIN team_registrations r ON r.team_id = teams.id
        LEFT JOIN participating_clubs clubs ON clubs.id = teams.club_id
        WHERE teams.tournament_id = :tournament_id
        ORDER BY teams.category_id NULLS LAST, r.registered_at NULLS LAST, teams.id
        """,
        values={"tournament_id": tournament_id},
    )
    places: dict[CategoryId | None, int] = {}
    registrations = []
    for row in rows:
        values = dict(row._mapping)
        place = None
        if values["registration_status"] == RegistrationStatus.WAITLIST.value:
            category_id = values["category_id"]
            place = places[category_id] = places.get(category_id, 0) + 1
        registrations.append(Registration.model_validate({**values, "waitlist_place": place}))
    return registrations


async def check_not_placed(tournament_id: TournamentId, team_id: TeamId) -> None:
    stages = await get_full_tournament_details(tournament_id)
    if any(
        input_.team_id == team_id
        for stage in stages
        for item in stage.stage_items
        for input_ in item.inputs
    ):
        raise bad_request("The team is placed in a group; remove it there before it leaves the cup")


async def update_registration(
    tournament_id: TournamentId, team_id: TeamId, body: RegistrationUpdateBody
) -> None:
    current = await database.fetch_val(
        "SELECT registration_status FROM teams WHERE id = :id AND tournament_id = :tournament_id",
        values={"id": team_id, "tournament_id": tournament_id},
    )
    if current is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the team")
    if not body.registration_status.participates and RegistrationStatus(current).participates:
        await check_not_placed(tournament_id, team_id)

    async with database.transaction():
        await database.execute(
            "UPDATE teams SET registration_status = :status WHERE id = :id",
            values={"status": body.registration_status.value, "id": team_id},
        )
        await database.execute(
            """
            INSERT INTO team_registrations (
                team_id, tournament_id, contact_name, contact_email, contact_phone, comment,
                paid, squad_reported
            )
            VALUES (
                :team_id, :tournament_id, :contact_name, :contact_email, :contact_phone,
                :comment, :paid, :squad_reported
            )
            ON CONFLICT (team_id) DO UPDATE SET
                contact_name = excluded.contact_name, contact_email = excluded.contact_email,
                contact_phone = excluded.contact_phone, comment = excluded.comment,
                paid = excluded.paid, squad_reported = excluded.squad_reported
            """,
            values={
                "team_id": team_id,
                "tournament_id": tournament_id,
                "contact_name": body.contact_name,
                "contact_email": None if body.contact_email is None else str(body.contact_email),
                "contact_phone": body.contact_phone,
                "comment": body.comment or None,
                "paid": body.paid,
                "squad_reported": body.squad_reported,
            },
        )
    if current == RegistrationStatus.WAITLIST.value and body.registration_status.participates:
        await queue_promotion_email(tournament_id, team_id)


async def promote_from_waitlist(tournament_id: TournamentId, category_id: CategoryId) -> TeamId:
    """Moves the first team on the waitlist of the class up: it takes part (approved)."""
    async with database.transaction():
        team_id = await database.fetch_val(
            """
            SELECT teams.id
            FROM teams
            LEFT JOIN team_registrations r ON r.team_id = teams.id
            WHERE teams.tournament_id = :tournament_id AND teams.category_id = :category_id
            AND teams.registration_status = 'WAITLIST'
            ORDER BY r.registered_at NULLS LAST, teams.id
            LIMIT 1
            FOR UPDATE OF teams
            """,
            values={"tournament_id": tournament_id, "category_id": category_id},
        )
        if team_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "There are no teams on the waitlist")
        await database.execute(
            "UPDATE teams SET registration_status = 'APPROVED' WHERE id = :id",
            values={"id": team_id},
        )
    await queue_promotion_email(tournament_id, TeamId(team_id))
    return TeamId(team_id)


async def set_registration_settings(
    tournament_id: TournamentId, category_id: CategoryId, body: RegistrationSettingsBody
) -> bool:
    updated = await database.fetch_val(
        """
        UPDATE categories
        SET registration_open = :registration_open,
            registration_deadline = :registration_deadline,
            max_teams = :max_teams, entry_fee = :entry_fee
        WHERE id = :id AND tournament_id = :tournament_id
        RETURNING id
        """,
        values={**body.model_dump(), "id": category_id, "tournament_id": tournament_id},
    )
    return updated is not None


async def set_entry_fees(tournament_id: TournamentId, body: EntryFeeBody) -> None:
    await database.execute(
        """
        UPDATE categories SET entry_fee = :entry_fee
        WHERE tournament_id = :tournament_id AND id = any(:ids)
        """,
        values={
            "entry_fee": body.entry_fee,
            "tournament_id": tournament_id,
            "ids": list(body.category_ids),
        },
    )


CSV_HEADERS = {
    "en": [
        "Class", "Team", "Club", "Status", "Waitlist place", "Contact person", "Email",
        "Phone", "Comment", "Registered", "Paid", "Squad reported", "Withdrawn",
    ],
    "nb": [
        "Klasse", "Lag", "Klubb", "Status", "Plass på venteliste", "Kontaktperson", "E-post",
        "Telefon", "Kommentar", "Påmeldt", "Betalt", "Tropp meldt", "Trukket",
    ],
}  # fmt: skip
YES_NO = {"en": ("Yes", "No"), "nb": ("Ja", "Nei")}


def registrations_csv(
    registrations: list[Registration], categories: list[Category], language: str
) -> str:
    """For Excel in Norway: UTF-8 with BOM and `;` between the columns."""
    language = language if language in CSV_HEADERS else "en"
    yes, no = YES_NO[language]
    names = {category.id: category.name for category in categories}
    return to_csv(
        CSV_HEADERS[language],
        (
            (
                names.get(r.category_id) if r.category_id is not None else "",
                r.team_name,
                r.club_name,
                r.registration_status.value,
                r.waitlist_place,
                r.contact_name,
                r.contact_email,
                r.contact_phone,
                r.comment,
                r.registered_at.strftime("%Y-%m-%d %H:%M UTC") if r.registered_at else "",
                yes if r.paid else no,
                yes if r.squad_reported else no,
                yes if r.withdrawn else no,
            )
            for r in registrations
        ),
    )
