from bracket.database import database
from bracket.models.db.category import Category, CategoryBody
from bracket.utils.id_types import CategoryId, TournamentId


def timing_values(body: CategoryBody) -> dict[str, object]:
    return {
        "duration_minutes": body.duration_minutes,
        "margin_minutes": body.margin_minutes,
        "min_rest_minutes": body.min_rest_minutes,
        "game_format": body.game_format.value if body.game_format is not None else None,
        "max_matches_per_day": body.max_matches_per_day,
    }


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
        INSERT INTO categories (
            created, tournament_id, name, age, results_public,
            duration_minutes, margin_minutes, min_rest_minutes, game_format, max_matches_per_day,
            kind, kind_note
        )
        VALUES (
            NOW(), :tournament_id, :name, :age, :results_public,
            :duration_minutes, :margin_minutes, :min_rest_minutes, :game_format,
            :max_matches_per_day, :kind, :kind_note
        )
        RETURNING *
        """
    result = await database.fetch_one(
        query=query,
        values={
            "tournament_id": tournament_id,
            "name": body.name,
            "age": body.age,
            "results_public": body.get_results_public(),
            "kind": body.kind.value if body.kind is not None else None,
            "kind_note": body.kind_note or None,
            **timing_values(body),
        },
    )
    assert result is not None, "Could not create category"
    return Category.model_validate(dict(result._mapping))


async def sql_update_category(
    tournament_id: TournamentId, category_id: CategoryId, body: CategoryBody
) -> Category | None:
    query = """
        UPDATE categories
        SET name = :name, age = :age, results_public = :results_public,
            duration_minutes = :duration_minutes, margin_minutes = :margin_minutes,
            min_rest_minutes = :min_rest_minutes, game_format = :game_format,
            max_matches_per_day = :max_matches_per_day, kind = :kind, kind_note = :kind_note
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
            "kind": body.kind.value if body.kind is not None else None,
            "kind_note": body.kind_note or None,
            **timing_values(body),
        },
    )
    return Category.model_validate(dict(result._mapping)) if result is not None else None


async def sql_delete_category(tournament_id: TournamentId, category_id: CategoryId) -> None:
    query = "DELETE FROM categories WHERE id = :category_id AND tournament_id = :tournament_id"
    await database.execute(
        query=query, values={"category_id": category_id, "tournament_id": tournament_id}
    )
