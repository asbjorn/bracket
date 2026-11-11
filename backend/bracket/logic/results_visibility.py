"""
Hiding results of age classes that don't allow publishing results.

NFF: in children's football (12 and younger), results and tables must not be published. The
organiser can still enter scores, but public (unauthenticated) responses only show whether a
match has been played.
"""

from decimal import Decimal
from typing import NoReturn

from fastapi import HTTPException
from starlette import status

from bracket.logic.ranking.statistics import START_ELO
from bracket.models.db.category import Category
from bracket.models.db.match import MatchWithDetails, MatchWithDetailsDefinitive
from bracket.models.db.stage_item import StageType
from bracket.models.db.stage_item_inputs import StageItemInput
from bracket.models.db.team import FullTeamWithPlayers
from bracket.models.db.util import RoundWithMatches, StageItemWithRounds, StageWithStageItems
from bracket.utils.id_types import CategoryId


def without_statistics(stage_item_input: StageItemInput) -> StageItemInput:
    return stage_item_input.model_copy(
        update={
            "points": Decimal("0.0"),
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
            "position": None,
        }
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


def hide_team_statistics_of_private_categories(
    teams: list[FullTeamWithPlayers], categories: list[Category]
) -> list[FullTeamWithPlayers]:
    """
    Resets the statistics stored on teams of classes where `results_public` is false. These
    fields are not written by any code today (results live on stage item inputs), but resetting
    them keeps the public API safe if that ever changes.
    """
    hidden_category_ids = {category.id for category in categories if not category.results_public}
    reset = {
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "elo_score": START_ELO,
        "swiss_score": Decimal("0.0"),
    }
    return [
        team.model_copy(update=reset) if team.category_id in hidden_category_ids else team
        for team in teams
    ]


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


ONLY_ROUND_ROBIN_WHEN_HIDDEN = (
    "Classes with hidden results only support round robin groups, "
    "because knockout and swiss rounds reveal the results"
)
NO_ADVANCING_WHEN_HIDDEN = (
    "In classes with hidden results, teams can't advance based on their placing, "
    "because that reveals the results"
)


def raise_bad_request(detail: str) -> NoReturn:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def check_stage_item_type_allowed(category: Category | None, stage_type: StageType) -> None:
    """
    Hiding scores is not enough when the structure itself reveals results: the winner of a
    knockout match appears in the next round, and swiss pairs teams by results. NFF children's
    football has no playoffs or rankings anyway, so classes with hidden results only get round
    robin groups (fixed schedules).
    """
    if category is not None and not category.results_public and stage_type != StageType.ROUND_ROBIN:
        raise_bad_request(ONLY_ROUND_ROBIN_WHEN_HIDDEN)


def check_advancing_allowed(category: Category | None) -> None:
    """
    Teams advancing by placing (e.g. "1st of group A") would reveal the group's table.
    """
    if category is not None and not category.results_public:
        raise_bad_request(NO_ADVANCING_WHEN_HIDDEN)


def check_category_can_hide_results(
    stages: list[StageWithStageItems], category_id: CategoryId
) -> None:
    """
    Before hiding the results of a class, its existing structure must not reveal them.
    """
    for stage in stages:
        if stage.category_id != category_id:
            continue
        for stage_item in stage.stage_items:
            if stage_item.type != StageType.ROUND_ROBIN:
                raise_bad_request(ONLY_ROUND_ROBIN_WHEN_HIDDEN)
            if any(input_.winner_from_stage_item_id is not None for input_ in stage_item.inputs):
                raise_bad_request(NO_ADVANCING_WHEN_HIDDEN)
