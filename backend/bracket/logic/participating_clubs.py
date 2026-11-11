"""
Participating clubs: the clubs that take part in a cup with one or more teams. A team belongs to
at most one club; the club keeps its teams apart in the group draw and is shown in listings.
"""

from fastapi import HTTPException
from heliclockter import datetime_utc
from starlette import status

from bracket.database import database
from bracket.logic.subscriptions import check_requirement
from bracket.models.db.participating_club import (
    ClubTeam,
    ParticipatingClub,
    ParticipatingClubCreateBody,
    ParticipatingClubUpdateBody,
    ParticipatingClubWithTeams,
)
from bracket.models.db.user import UserPublic
from bracket.sql.teams import get_teams_with_members
from bracket.utils.errors import UniqueIndex, check_unique_constraint_violation
from bracket.utils.id_types import CategoryId, ParticipatingClubId, TeamId, TournamentId


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail)


async def get_participating_clubs(tournament_id: TournamentId) -> list[ParticipatingClubWithTeams]:
    clubs = await database.fetch_all(
        "SELECT * FROM participating_clubs WHERE tournament_id = :tournament_id ORDER BY name",
        values={"tournament_id": tournament_id},
    )
    teams = await database.fetch_all(
        """
        SELECT id, name, category_id, club_id FROM teams
        WHERE tournament_id = :tournament_id AND club_id IS NOT NULL
        ORDER BY name
        """,
        values={"tournament_id": tournament_id},
    )
    teams_by_club: dict[int, list[ClubTeam]] = {}
    for team in teams:
        teams_by_club.setdefault(team["club_id"], []).append(
            ClubTeam(id=team["id"], name=team["name"], category_id=team["category_id"])
        )
    return [
        ParticipatingClubWithTeams(**dict(club._mapping), teams=teams_by_club.get(club["id"], []))
        for club in clubs
    ]


async def get_club_names(tournament_id: TournamentId) -> dict[ParticipatingClubId, str]:
    rows = await database.fetch_all(
        "SELECT id, name FROM participating_clubs WHERE tournament_id = :tournament_id",
        values={"tournament_id": tournament_id},
    )
    return {ParticipatingClubId(row["id"]): row["name"] for row in rows}


async def get_participating_club(
    tournament_id: TournamentId, club_id: ParticipatingClubId
) -> ParticipatingClub | None:
    row = await database.fetch_one(
        "SELECT * FROM participating_clubs WHERE id = :id AND tournament_id = :tournament_id",
        values={"id": club_id, "tournament_id": tournament_id},
    )
    return None if row is None else ParticipatingClub.model_validate(dict(row._mapping))


async def find_or_create_club(tournament_id: TournamentId, name: str) -> ParticipatingClubId:
    """The club with this name (ignoring case), created if it doesn't exist yet."""
    name = name.strip()
    club_id = await database.fetch_val(
        """
        INSERT INTO participating_clubs (tournament_id, name, created)
        VALUES (:tournament_id, :name, NOW())
        ON CONFLICT (tournament_id, lower(name)) DO NOTHING
        RETURNING id
        """,
        values={"tournament_id": tournament_id, "name": name},
    )
    if club_id is None:
        club_id = await database.fetch_val(
            """
            SELECT id FROM participating_clubs
            WHERE tournament_id = :tournament_id AND lower(name) = lower(:name)
            """,
            values={"tournament_id": tournament_id, "name": name},
        )
    return ParticipatingClubId(int(club_id))


async def check_teams(
    tournament_id: TournamentId,
    team_ids: list[TeamId],
    allowed_club: ParticipatingClubId | None,
) -> None:
    """The teams exist in this tournament and have no club (or already are in `allowed_club`)."""
    if len(team_ids) < 1:
        return
    rows = await database.fetch_all(
        "SELECT id, club_id FROM teams WHERE id = any(:ids) AND tournament_id = :tournament_id",
        values={"ids": team_ids, "tournament_id": tournament_id},
    )
    if len(rows) != len(team_ids):
        raise bad_request("Some of the teams don't exist in this tournament")
    if any(row["club_id"] is not None and row["club_id"] != allowed_club for row in rows):
        raise bad_request("Some of the teams already belong to another club")


async def check_categories(tournament_id: TournamentId, category_ids: set[CategoryId]) -> None:
    if len(category_ids) < 1:
        return
    count = await database.fetch_val(
        "SELECT count(*) FROM categories WHERE id = any(:ids) AND tournament_id = :tournament_id",
        values={"ids": list(category_ids), "tournament_id": tournament_id},
    )
    if int(count) != len(category_ids):
        raise bad_request("Some of the classes don't exist in this tournament")


async def lock_tournament(tournament_id: TournamentId) -> None:
    """Changes to the clubs and teams of a cup happen one at a time (checks then hold)."""
    await database.execute(
        "SELECT id FROM tournaments WHERE id = :id FOR UPDATE", values={"id": tournament_id}
    )


async def create_participating_club(
    tournament_id: TournamentId, body: ParticipatingClubCreateBody, user: UserPublic
) -> ParticipatingClubId:
    await check_categories(
        tournament_id,
        {team.category_id for team in body.new_teams if team.category_id is not None},
    )
    async with database.transaction():
        await lock_tournament(tournament_id)
        await check_teams(tournament_id, body.team_ids, allowed_club=None)
        if body.new_teams:
            existing_teams = await get_teams_with_members(tournament_id)
            check_requirement(existing_teams, user, "max_teams", additions=len(body.new_teams))

        with check_unique_constraint_violation(
            {UniqueIndex.ix_participating_clubs_tournament_id_lower_name}
        ):
            club_id = ParticipatingClubId(
                await database.fetch_val(
                    """
                    INSERT INTO participating_clubs (tournament_id, name, created)
                    VALUES (:tournament_id, :name, NOW())
                    RETURNING id
                    """,
                    values={"tournament_id": tournament_id, "name": body.name},
                )
            )
        for team in body.new_teams:
            await database.execute(
                """
                INSERT INTO teams (
                    name, created, tournament_id, active, elo_score, swiss_score, wins, draws,
                    losses, category_id, club_id
                )
                VALUES (
                    :name, :created, :tournament_id, true, 1200, 0, 0, 0, 0, :category_id,
                    :club_id
                )
                """,
                values={
                    "name": team.name,
                    "created": datetime_utc.now(),
                    "tournament_id": tournament_id,
                    "category_id": team.category_id,
                    "club_id": club_id,
                },
            )
        await set_club_of_teams(tournament_id, body.team_ids, club_id)
    return club_id


async def set_club_of_teams(
    tournament_id: TournamentId, team_ids: list[TeamId], club_id: ParticipatingClubId | None
) -> None:
    if len(team_ids) < 1:
        return
    await database.execute(
        """
        UPDATE teams SET club_id = :club_id
        WHERE id = any(:ids) AND tournament_id = :tournament_id
        """,
        values={"club_id": club_id, "ids": team_ids, "tournament_id": tournament_id},
    )


async def update_participating_club(
    tournament_id: TournamentId, club_id: ParticipatingClubId, body: ParticipatingClubUpdateBody
) -> None:
    async with database.transaction():
        await lock_tournament(tournament_id)
        if await get_participating_club(tournament_id, club_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the club")
        await check_teams(tournament_id, body.team_ids, allowed_club=club_id)
        with check_unique_constraint_violation(
            {UniqueIndex.ix_participating_clubs_tournament_id_lower_name}
        ):
            await database.execute(
                "UPDATE participating_clubs SET name = :name WHERE id = :id",
                values={"name": body.name, "id": club_id},
            )
        # Exactly these teams: the others leave the club
        await database.execute(
            """
            UPDATE teams SET club_id = NULL
            WHERE club_id = :club_id AND tournament_id = :tournament_id AND NOT (id = any(:ids))
            """,
            values={"club_id": club_id, "tournament_id": tournament_id, "ids": body.team_ids},
        )
        await set_club_of_teams(tournament_id, body.team_ids, club_id)


async def delete_participating_club(
    tournament_id: TournamentId, club_id: ParticipatingClubId
) -> None:
    """The teams stay; they just no longer belong to a club."""
    async with database.transaction():
        if await get_participating_club(tournament_id, club_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the club")
        await database.execute(
            "UPDATE teams SET club_id = NULL WHERE club_id = :club_id",
            values={"club_id": club_id},
        )
        await database.execute(
            "DELETE FROM participating_clubs WHERE id = :id AND tournament_id = :tournament_id",
            values={"id": club_id, "tournament_id": tournament_id},
        )
