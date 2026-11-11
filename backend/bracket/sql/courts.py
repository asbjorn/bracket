from bracket.database import database
from bracket.models.db.court import Court, CourtBody
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
