"""
Importing players from a file (the frontend parses CSV and sends rows): new players are
created, names that already exist are skipped, and players can be put on a team at once.
"""

from fastapi import HTTPException
from heliclockter import datetime_utc
from pydantic import BaseModel, Field
from starlette import status

from bracket.database import database
from bracket.logic.ranking.statistics import START_ELO
from bracket.logic.subscriptions import check_requirement
from bracket.models.db.player import PlayerName
from bracket.models.db.user import UserPublic
from bracket.sql.players import get_all_players_in_tournament
from bracket.sql.teams import get_teams_by_id
from bracket.utils.id_types import TeamId, TournamentId

MAX_IMPORT_ROWS = 2000


class PlayerImportRow(BaseModel):
    name: PlayerName
    team_id: TeamId | None = None
    # Empty: `active` of the import
    active: bool | None = None


class PlayerImportBody(BaseModel):
    rows: list[PlayerImportRow] = Field(min_length=1, max_length=MAX_IMPORT_ROWS)
    active: bool = True


class PlayerImportResult(BaseModel):
    created: int
    # Existing players put on a team they weren't on
    added_to_team: int
    # Names that already existed (or appeared twice in the file)
    skipped: list[str]
    # Players not put on their team because they're on another team already (when the cup
    # doesn't allow players in several teams)
    not_added_to_team: list[str] = []


def name_key(name: str) -> str:
    return " ".join(name.split()).casefold()


async def import_players(
    tournament_id: TournamentId, body: PlayerImportBody, user: UserPublic
) -> PlayerImportResult:
    team_ids = {row.team_id for row in body.rows if row.team_id is not None}
    teams = await get_teams_by_id(team_ids, tournament_id)
    if len(teams) != len(team_ids):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Some of the teams don't exist in this cup"
        )

    async with database.transaction():
        # One import at a time per cup, so two imports can't create the same names
        await database.execute(
            "SELECT id FROM tournaments WHERE id = :id FOR UPDATE", values={"id": tournament_id}
        )
        existing = await get_all_players_in_tournament(tournament_id)
        player_id_by_name = {name_key(player.name): player.id for player in existing}

        new_rows: list[PlayerImportRow] = []
        seen: set[str] = set()
        skipped: list[str] = []
        for row in body.rows:
            key = name_key(row.name)
            if key in seen or key in player_id_by_name:
                skipped.append(row.name)
            else:
                new_rows.append(row)
            seen.add(key)
        check_requirement(existing, user, "max_players", additions=len(new_rows))

        for row in new_rows:
            player_id = await database.fetch_val(
                """
                INSERT INTO players (name, active, created, tournament_id, elo_score, swiss_score,
                                     wins, draws, losses)
                VALUES (:name, :active, :created, :tournament_id, :elo, 0, 0, 0, 0)
                RETURNING id
                """,
                values={
                    "name": " ".join(row.name.split()),
                    "active": body.active if row.active is None else row.active,
                    "created": datetime_utc.now(),
                    "tournament_id": tournament_id,
                    "elo": float(START_ELO),
                },
            )
            player_id_by_name[name_key(row.name)] = player_id

        new_keys = {name_key(row.name) for row in new_rows}
        several_teams = await database.fetch_val(
            "SELECT players_can_be_in_multiple_teams FROM tournaments WHERE id = :id",
            values={"id": tournament_id},
        )
        added_to_team = 0
        not_added: list[str] = []
        for row in body.rows:
            if row.team_id is None:
                continue
            player_id = player_id_by_name[name_key(row.name)]
            if not several_teams:
                other_team = await database.fetch_val(
                    """
                    SELECT team_id FROM players_x_teams
                    WHERE player_id = :player_id AND team_id <> :team_id LIMIT 1
                    """,
                    values={"player_id": player_id, "team_id": row.team_id},
                )
                if other_team is not None:
                    not_added.append(row.name)
                    continue
            linked = await database.fetch_val(
                """
                INSERT INTO players_x_teams (player_id, team_id)
                SELECT :player_id, :team_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM players_x_teams
                    WHERE player_id = :player_id AND team_id = :team_id
                )
                RETURNING id
                """,
                values={"player_id": player_id, "team_id": row.team_id},
            )
            # New players are counted as created; existing ones put on a team are counted here
            if linked is not None and name_key(row.name) not in new_keys:
                added_to_team += 1

    return PlayerImportResult(
        created=len(new_rows),
        added_to_team=added_to_team,
        skipped=skipped,
        not_added_to_team=not_added,
    )
