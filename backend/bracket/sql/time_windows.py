from bracket.database import database
from bracket.models.db.time_window import TimeWindow, TimeWindowBody
from bracket.utils.id_types import TournamentId


async def get_time_windows(tournament_id: TournamentId) -> list[TimeWindow]:
    query = """
        SELECT *
        FROM time_windows
        WHERE time_windows.tournament_id = :tournament_id
        ORDER BY start_time
        """
    result = await database.fetch_all(query=query, values={"tournament_id": tournament_id})
    return [TimeWindow.model_validate(dict(x._mapping)) for x in result]


async def sql_replace_time_windows(
    tournament_id: TournamentId, time_windows: list[TimeWindowBody]
) -> None:
    async with database.transaction():
        await database.execute(
            "DELETE FROM time_windows WHERE tournament_id = :tournament_id",
            values={"tournament_id": tournament_id},
        )
        for window in time_windows:
            await database.execute(
                """
                INSERT INTO time_windows (tournament_id, start_time, end_time)
                VALUES (:tournament_id, :start_time, :end_time)
                """,
                values={
                    "tournament_id": tournament_id,
                    "start_time": window.start_time,
                    "end_time": window.end_time,
                },
            )
