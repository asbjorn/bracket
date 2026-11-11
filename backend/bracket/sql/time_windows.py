from collections import defaultdict

from bracket.database import database
from bracket.models.db.time_window import TimeWindow, TimeWindowBody
from bracket.utils.id_types import CategoryId, CourtId, TournamentId

# Windows of the cup itself; pitches and classes can have their own (opening hours, days)
CUP_WINDOWS = "court_id IS NULL AND category_id IS NULL"


async def get_time_windows(tournament_id: TournamentId) -> list[TimeWindow]:
    query = f"""
        SELECT *
        FROM time_windows
        WHERE time_windows.tournament_id = :tournament_id
        AND {CUP_WINDOWS}
        ORDER BY start_time
        """
    result = await database.fetch_all(query=query, values={"tournament_id": tournament_id})
    return [TimeWindow.model_validate(dict(x._mapping)) for x in result]


async def get_own_time_windows(
    tournament_id: TournamentId,
) -> tuple[dict[CourtId, list[TimeWindow]], dict[CategoryId, list[TimeWindow]]]:
    """The opening hours of pitches and the days/hours of classes that have their own."""
    rows = await database.fetch_all(
        f"""
        SELECT * FROM time_windows
        WHERE tournament_id = :tournament_id AND NOT ({CUP_WINDOWS})
        ORDER BY start_time
        """,
        values={"tournament_id": tournament_id},
    )
    per_court: dict[CourtId, list[TimeWindow]] = defaultdict(list)
    per_category: dict[CategoryId, list[TimeWindow]] = defaultdict(list)
    for row in rows:
        window = TimeWindow.model_validate(dict(row._mapping))
        if row["court_id"] is not None:
            per_court[CourtId(row["court_id"])].append(window)
        else:
            per_category[CategoryId(row["category_id"])].append(window)
    return dict(per_court), dict(per_category)


async def sql_replace_time_windows(
    tournament_id: TournamentId,
    time_windows: list[TimeWindowBody],
    *,
    court_id: CourtId | None = None,
    category_id: CategoryId | None = None,
) -> None:
    """
    Replaces the windows of the cup, or (with `court_id` / `category_id`) of one pitch or class;
    an empty list there means: the windows of the cup.
    """
    owner = {"court_id": court_id, "category_id": category_id}
    async with database.transaction():
        await database.execute(
            """
            DELETE FROM time_windows
            WHERE tournament_id = :tournament_id
            AND court_id IS NOT DISTINCT FROM :court_id
            AND category_id IS NOT DISTINCT FROM :category_id
            """,
            values={"tournament_id": tournament_id, **owner},
        )
        for window in time_windows:
            await database.execute(
                """
                INSERT INTO time_windows (
                    tournament_id, start_time, end_time, court_id, category_id
                )
                VALUES (:tournament_id, :start_time, :end_time, :court_id, :category_id)
                """,
                values={
                    "tournament_id": tournament_id,
                    "start_time": window.start_time,
                    "end_time": window.end_time,
                    **owner,
                },
            )
        if court_id is None and category_id is None and len(time_windows) > 0:
            # The cup starts when it starts playing (the list and the settings show this)
            await database.execute(
                f"""
                UPDATE tournaments SET start_time = (
                    SELECT min(start_time) FROM time_windows
                    WHERE tournament_id = :tournament_id AND {CUP_WINDOWS}
                )
                WHERE id = :tournament_id
                """,
                values={"tournament_id": tournament_id},
            )
