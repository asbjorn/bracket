from heliclockter import datetime_utc

from bracket.database import database
from bracket.models.db.court import Court, CourtBody, CourtsMultiBody, CourtToInsert
from bracket.schema import courts
from bracket.utils.id_types import CourtId, TournamentId


async def get_all_courts_in_tournament(tournament_id: TournamentId) -> list[Court]:
    query = """
        SELECT *
        FROM courts
        WHERE courts.tournament_id = :tournament_id
        ORDER BY name
        """
    result = await database.fetch_all(query=query, values={"tournament_id": tournament_id})
    return [Court.model_validate(dict(x._mapping)) for x in result]


async def update_court(
    tournament_id: TournamentId, court_id: CourtId, court_body: CourtBody
) -> list[Court]:
    query = """
        UPDATE courts
        SET name = :name, game_format = :game_format
        WHERE courts.tournament_id = :tournament_id
        AND courts.id = :court_id
        """
    result = await database.fetch_all(
        query=query,
        values={
            "tournament_id": tournament_id,
            "court_id": court_id,
            "name": court_body.name,
            "game_format": court_body.game_format.value if court_body.game_format else None,
        },
    )
    return [Court.model_validate(dict(x._mapping)) for x in result]


async def sql_delete_court(tournament_id: TournamentId, court_id: CourtId) -> None:
    query = "DELETE FROM courts WHERE id = :court_id AND tournament_id = :tournament_id"
    await database.fetch_one(
        query=query, values={"court_id": court_id, "tournament_id": tournament_id}
    )


async def sql_delete_courts_of_tournament(tournament_id: TournamentId) -> None:
    query = "DELETE FROM courts WHERE tournament_id = :tournament_id"
    await database.fetch_one(query=query, values={"tournament_id": tournament_id})


def next_court_number(existing_names: list[str], prefix: str) -> int:
    """
    Continues the numbering of courts named "<prefix> <number>", e.g. after "Bane 3" comes 4.
    """
    numbers = [
        int(name[len(prefix) :].strip())
        for name in existing_names
        if name.startswith(prefix) and name[len(prefix) :].strip().isdigit()
    ]
    return max(numbers, default=0) + 1


async def sql_create_courts(tournament_id: TournamentId, body: CourtsMultiBody) -> None:
    """Creates `count` courts, continuing the numbering of courts with the same prefix."""
    existing_courts = await get_all_courts_in_tournament(tournament_id)
    first = next_court_number([court.name for court in existing_courts], body.name_prefix)
    async with database.transaction():
        for number in range(first, first + body.count):
            full_id = await database.execute(
                query=courts.insert(),
                values=CourtToInsert(
                    name=f"{body.name_prefix} {number}",
                    game_format=body.game_format,
                    created=datetime_utc.now(),
                    tournament_id=tournament_id,
                ).model_dump(),
            )
            # A split pitch: its parts "Bane 1A", "Bane 1B", ...
            for letter in "ABCD"[: body.split_into or 0]:
                await database.execute(
                    query=courts.insert(),
                    values=CourtToInsert(
                        name=f"{body.name_prefix} {number}{letter}",
                        game_format=body.part_format,
                        created=datetime_utc.now(),
                        tournament_id=tournament_id,
                    ).model_dump()
                    | {"parent_court_id": full_id},
                )
