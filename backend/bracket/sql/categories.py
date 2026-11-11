from bracket.database import database
from bracket.models.db.category import Category, CategoryBody
from bracket.utils.id_types import CategoryId, TournamentId


async def get_all_categories_in_tournament(tournament_id: TournamentId) -> list[Category]:
    query = """
        SELECT *
        FROM categories
        WHERE categories.tournament_id = :tournament_id
        ORDER BY age NULLS LAST, name
        """
    result = await database.fetch_all(query=query, values={"tournament_id": tournament_id})
    return [Category.model_validate(dict(x._mapping)) for x in result]


async def get_category_by_id(
    tournament_id: TournamentId, category_id: CategoryId
) -> Category | None:
    query = """
        SELECT *
        FROM categories
        WHERE categories.tournament_id = :tournament_id
        AND categories.id = :category_id
        """
    result = await database.fetch_one(
        query=query, values={"tournament_id": tournament_id, "category_id": category_id}
    )
    return Category.model_validate(dict(result._mapping)) if result is not None else None


async def sql_create_category(tournament_id: TournamentId, body: CategoryBody) -> Category:
    query = """
        INSERT INTO categories (created, tournament_id, name, age, results_public)
        VALUES (NOW(), :tournament_id, :name, :age, :results_public)
        RETURNING *
        """
    result = await database.fetch_one(
        query=query,
        values={
            "tournament_id": tournament_id,
            "name": body.name,
            "age": body.age,
            "results_public": body.get_results_public(),
        },
    )
    assert result is not None, "Could not create category"
    return Category.model_validate(dict(result._mapping))


async def sql_update_category(
    tournament_id: TournamentId, category_id: CategoryId, body: CategoryBody
) -> Category | None:
    query = """
        UPDATE categories
        SET name = :name, age = :age, results_public = :results_public
        WHERE categories.tournament_id = :tournament_id
        AND categories.id = :category_id
        RETURNING *
        """
    result = await database.fetch_one(
        query=query,
        values={
            "tournament_id": tournament_id,
            "category_id": category_id,
            "name": body.name,
            "age": body.age,
            "results_public": body.get_results_public(),
        },
    )
    return Category.model_validate(dict(result._mapping)) if result is not None else None


async def sql_delete_category(tournament_id: TournamentId, category_id: CategoryId) -> None:
    query = "DELETE FROM categories WHERE id = :category_id AND tournament_id = :tournament_id"
    await database.execute(
        query=query, values={"category_id": category_id, "tournament_id": tournament_id}
    )
