"""
Hiding results of age classes that don't allow publishing results.

NFF: in children's football (12 and younger), results and tables must not be published. The
organiser can still enter scores, but public (unauthenticated) responses only show whether a
match has been played.
"""

from decimal import Decimal

from bracket.models.db.category import Category
from bracket.models.db.match import MatchWithDetails, MatchWithDetailsDefinitive
from bracket.models.db.stage_item_inputs import StageItemInput
from bracket.models.db.util import RoundWithMatches, StageItemWithRounds, StageWithStageItems


def without_statistics(stage_item_input: StageItemInput) -> StageItemInput:
    return stage_item_input.model_copy(
        update={"points": Decimal("0.0"), "wins": 0, "draws": 0, "losses": 0}
    )


def without_score(
    match: MatchWithDetailsDefinitive | MatchWithDetails,
) -> MatchWithDetailsDefinitive | MatchWithDetails:
    update: dict[str, object] = {"stage_item_input1_score": 0, "stage_item_input2_score": 0}
    if match.stage_item_input1 is not None:
        update["stage_item_input1"] = without_statistics(match.stage_item_input1)
    if match.stage_item_input2 is not None:
        update["stage_item_input2"] = without_statistics(match.stage_item_input2)
    return match.model_copy(update=update)


def without_results_round(round_: RoundWithMatches) -> RoundWithMatches:
    return round_.model_copy(update={"matches": [without_score(m) for m in round_.matches]})


def without_results_stage_item(stage_item: StageItemWithRounds) -> StageItemWithRounds:
    return stage_item.model_copy(
        update={
            "inputs": [without_statistics(input_) for input_ in stage_item.inputs],
            "rounds": [without_results_round(round_) for round_ in stage_item.rounds],
        }
    )


def hide_results_of_private_categories(
    stages: list[StageWithStageItems], categories: list[Category]
) -> list[StageWithStageItems]:
    """
    Removes scores and ranking statistics from stages of classes where `results_public` is false.
    Whether a match has been played (`played`) stays visible.
    """
    hidden_category_ids = {category.id for category in categories if not category.results_public}
    return [
        stage.model_copy(
            update={"stage_items": [without_results_stage_item(si) for si in stage.stage_items]}
        )
        if stage.category_id in hidden_category_ids
        else stage
        for stage in stages
    ]
