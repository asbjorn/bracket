"""
How long matches take and how long teams rest between matches.

The duration and margin (changeover time) of a match are its own custom values if set,
otherwise those of its age class, otherwise the tournament defaults. `sql_apply_default_timing`
stores this on every match, so code that schedules matches can use `match.duration_minutes`.
"""

from bracket.models.db.category import Category
from bracket.models.db.tournament import Tournament
from bracket.models.db.util import StageWithStageItems
from bracket.utils.id_types import CategoryId, MatchId


def get_min_rest_minutes(category: Category | None, tournament: Tournament) -> int:
    if category is not None and category.min_rest_minutes is not None:
        return category.min_rest_minutes
    return tournament.min_rest_minutes


def get_category_per_match(
    stages: list[StageWithStageItems], categories: list[Category]
) -> dict[MatchId, Category | None]:
    categories_by_id: dict[CategoryId, Category] = {c.id: c for c in categories}
    return {
        match.id: categories_by_id.get(stage.category_id) if stage.category_id else None
        for stage in stages
        for stage_item in stage.stage_items
        for round_ in stage_item.rounds
        for match in round_.matches
    }
