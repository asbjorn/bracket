"""Teams that must never play at the same time: explicit pairs, and clubs with `no_overlap`."""

from bracket.database import database
from bracket.utils.id_types import TeamId, TournamentId


async def get_team_conflicts(tournament_id: TournamentId) -> list[tuple[TeamId, TeamId]]:
    rows = await database.fetch_all(
        """
        SELECT team1_id, team2_id FROM team_conflicts
        WHERE tournament_id = :tournament_id
        ORDER BY team1_id, team2_id
        """,
        values={"tournament_id": tournament_id},
    )
    return [(TeamId(row["team1_id"]), TeamId(row["team2_id"])) for row in rows]


async def sql_set_team_conflicts(
    tournament_id: TournamentId, team_id: TeamId, other_team_ids: set[TeamId]
) -> None:
    """Sets exactly which teams can't play at the same time as `team_id`."""
    async with database.transaction():
        await database.execute(
            """
            DELETE FROM team_conflicts
            WHERE tournament_id = :tournament_id
            AND (team1_id = :team_id OR team2_id = :team_id)
            """,
            values={"tournament_id": tournament_id, "team_id": team_id},
        )
        for other in sorted(other_team_ids - {team_id}):
            await database.execute(
                """
                INSERT INTO team_conflicts (tournament_id, team1_id, team2_id)
                VALUES (:tournament_id, :team1_id, :team2_id)
                """,
                values={
                    "tournament_id": tournament_id,
                    "team1_id": min(team_id, other),
                    "team2_id": max(team_id, other),
                },
            )


async def get_no_overlap_club_teams(tournament_id: TournamentId) -> dict[int, list[TeamId]]:
    """The teams per participating club whose teams must not play at the same time."""
    rows = await database.fetch_all(
        """
        SELECT clubs.id AS club_id, teams.id AS team_id
        FROM participating_clubs clubs
        JOIN teams ON teams.club_id = clubs.id
        WHERE clubs.tournament_id = :tournament_id AND clubs.no_overlap IS TRUE
        """,
        values={"tournament_id": tournament_id},
    )
    result: dict[int, list[TeamId]] = {}
    for row in rows:
        result.setdefault(int(row["club_id"]), []).append(TeamId(row["team_id"]))
    return result
