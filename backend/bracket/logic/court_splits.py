"""
Split pitches as a tree: a full pitch can be split into parts, and a part can be split again
(e.g. 11er › 7er › 5er › 3er). Undoing a split removes all parts below a pitch.
"""

from fastapi import HTTPException
from pydantic import BaseModel
from starlette import status

from bracket.database import database
from bracket.models.db.court import Court
from bracket.utils.id_types import CourtId, MatchId, TournamentId


class MatchOnCourt(BaseModel):
    id: MatchId
    court_id: CourtId
    court_name: str
    start_time: str | None
    played: bool
    started: bool


def descendant_ids(court_id: CourtId, courts: list[Court]) -> list[CourtId]:
    """All parts below a pitch, at any depth."""
    children: dict[CourtId, list[CourtId]] = {}
    for court in courts:
        if court.parent_court_id is not None:
            children.setdefault(court.parent_court_id, []).append(court.id)
    result: list[CourtId] = []
    todo = list(children.get(court_id, []))
    while todo:
        child = todo.pop()
        if child not in result:
            result.append(child)
            todo += children.get(child, [])
    return result


def part_suffixes(parent_name: str, parts: int) -> list[str]:
    """Letters below a numbered pitch ("Bane 3" › "Bane 3A"), digits below a letter ("3A1")."""
    if parent_name[-1:].isalpha():
        return [str(number) for number in range(1, parts + 1)]
    return list("ABCD"[:parts])


async def get_matches_on_courts(
    tournament_id: TournamentId, court_ids: list[CourtId], courts: list[Court]
) -> list[MatchOnCourt]:
    if len(court_ids) < 1:
        return []
    names = {court.id: court.name for court in courts}
    rows = await database.fetch_all(
        """
        SELECT matches.id, matches.court_id, matches.start_time, matches.played,
               matches.started_at IS NOT NULL AS started
        FROM matches
        JOIN rounds ON rounds.id = matches.round_id
        JOIN stage_items ON stage_items.id = rounds.stage_item_id
        JOIN stages ON stages.id = stage_items.stage_id
        WHERE stages.tournament_id = :tournament_id AND matches.court_id = any(:court_ids)
        ORDER BY matches.start_time NULLS LAST, matches.id
        """,
        values={"tournament_id": tournament_id, "court_ids": court_ids},
    )
    return [
        MatchOnCourt(
            id=row["id"],
            court_id=row["court_id"],
            court_name=names.get(row["court_id"], ""),
            start_time=None if row["start_time"] is None else row["start_time"].isoformat(),
            played=row["played"],
            started=row["started"],
        )
        for row in rows
    ]


async def undo_split(
    tournament_id: TournamentId,
    court_id: CourtId,
    courts: list[Court],
    *,
    unschedule_matches: bool,
) -> None:
    """
    Removes all parts below a pitch. Matches planned on them are only taken off (no pitch, no
    time) when `unschedule_matches`; played or started matches always block it.
    """
    parts = descendant_ids(court_id, courts)
    if len(parts) < 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This pitch isn't split")
    async with database.transaction():
        await database.execute(
            "SELECT id FROM courts WHERE tournament_id = :tournament_id FOR UPDATE",
            values={"tournament_id": tournament_id},
        )
        on_parts = await get_matches_on_courts(tournament_id, parts, courts)
        fixed = [match for match in on_parts if match.played or match.started]
        if fixed:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"{len(fixed)} played or started matches are on the parts of this pitch, "
                "so the split can't be undone",
            )
        if on_parts and not unschedule_matches:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{len(on_parts)} matches are planned on the parts of this pitch",
            )
        if on_parts:
            await database.execute(
                """
                UPDATE matches SET court_id = NULL, start_time = NULL, position_in_schedule = NULL
                WHERE id = any(:match_ids)
                """,
                values={"match_ids": [match.id for match in on_parts]},
            )
        # Deleting the direct parts deletes the parts below them (ON DELETE CASCADE)
        await database.execute(
            """
            DELETE FROM courts
            WHERE tournament_id = :tournament_id AND parent_court_id = :court_id
            """,
            values={"tournament_id": tournament_id, "court_id": court_id},
        )
