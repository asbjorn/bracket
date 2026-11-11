"""
Checks of an age class against the NFF rules (Breddereglement), shown as warnings to organisers.

- § 6-4: in tournaments for the 13-year class and younger, every team gets at least 3 matches.
- § 6-5: in children's football (12 and younger) results and tables are not published.
"""

from enum import auto

from pydantic import BaseModel

from bracket.models.db.category import YOUTH_FOOTBALL_MIN_AGE, Category
from bracket.models.db.match import MatchWithDetails, MatchWithDetailsDefinitive
from bracket.models.db.stage_item_inputs import StageItemInputFinal, StageItemInputTentative
from bracket.models.db.team import FullTeamWithPlayers
from bracket.models.db.util import StageItemWithRounds, StageWithStageItems
from bracket.utils.id_types import CategoryId, StageItemId
from bracket.utils.types import EnumAutoStr

MIN_MATCHES_PER_TEAM = 3
MIN_MATCHES_MAX_AGE = 13


class CategoryWarningCode(EnumAutoStr):
    TOO_FEW_MATCHES = auto()
    UNPLACED_TEAMS = auto()
    CHILDREN_RESULTS_PUBLIC = auto()


class CategoryWarning(BaseModel):
    code: CategoryWarningCode
    # TOO_FEW_MATCHES: the lowest guaranteed number of matches of a team
    minimum_matches: int | None = None
    # TOO_FEW_MATCHES and UNPLACED_TEAMS: the teams involved
    team_names: list[str] = []


def matches_of_stage_item(
    stage_item: StageItemWithRounds,
) -> list[MatchWithDetailsDefinitive | MatchWithDetails]:
    return [
        match for round_ in stage_item.rounds if not round_.is_draft for match in round_.matches
    ]


def guaranteed_matches_within_stage_item(stage_item: StageItemWithRounds) -> int:
    """
    The number of matches every team in this stage item plays for sure: the minimum over its
    inputs of the matches they are scheduled in. In a knockout bracket that's 1 (the first round),
    in a round robin group of n teams it's n - 1.
    """
    if len(stage_item.inputs) < 1:
        return 0

    matches = matches_of_stage_item(stage_item)
    return min(
        sum(
            1
            for match in matches
            if input_.id in (match.stage_item_input1_id, match.stage_item_input2_id)
        )
        for input_ in stage_item.inputs
    )


def get_guaranteed_matches_per_stage_item(
    stages: list[StageWithStageItems],
) -> dict[StageItemId, int]:
    """
    For every stage item: the matches a team placed in it plays for sure, in this stage item and
    in later stages. Teams advance by placing (e.g. "2nd of group A"); since the placing is not
    known beforehand, the worst case placing counts. Placings that don't advance add nothing.
    """
    stage_items = {
        stage_item.id: stage_item for stage in stages for stage_item in stage.stage_items
    }
    # (source stage item, placing) -> stage item that this placing advances to
    advances_to: dict[tuple[StageItemId, int], StageItemId] = {
        (input_.winner_from_stage_item_id, input_.winner_position): stage_item.id
        for stage_item in stage_items.values()
        for input_ in stage_item.inputs
        if isinstance(input_, StageItemInputTentative)
    }

    result: dict[StageItemId, int] = {}

    def guaranteed(stage_item_id: StageItemId) -> int:
        if stage_item_id not in result:
            stage_item = stage_items[stage_item_id]
            later = min(
                (
                    guaranteed(advances_to[(stage_item_id, position)])
                    if (stage_item_id, position) in advances_to
                    else 0
                )
                for position in range(1, stage_item.team_count + 1)
            )
            result[stage_item_id] = guaranteed_matches_within_stage_item(stage_item) + later
        return result[stage_item_id]

    for stage_item_id in stage_items:
        guaranteed(stage_item_id)
    return result


def get_category_warnings(
    category: Category,
    teams: list[FullTeamWithPlayers],
    stages: list[StageWithStageItems],
) -> list[CategoryWarning]:
    """
    `teams` and `stages` are those of this category.
    """
    warnings: list[CategoryWarning] = []

    if (
        category.age is not None
        and category.age < YOUTH_FOOTBALL_MIN_AGE
        and category.results_public
    ):
        warnings.append(CategoryWarning(code=CategoryWarningCode.CHILDREN_RESULTS_PUBLIC))

    guaranteed_per_stage_item = get_guaranteed_matches_per_stage_item(stages)
    stage_items_per_team: dict[int, list[StageItemId]] = {}
    for stage in stages:
        for stage_item in stage.stage_items:
            for input_ in stage_item.inputs:
                if isinstance(input_, StageItemInputFinal):
                    stage_items_per_team.setdefault(input_.team_id, []).append(stage_item.id)

    active_teams = sorted((team for team in teams if team.active), key=lambda team: team.name)
    unplaced = [team.name for team in active_teams if team.id not in stage_items_per_team]
    if unplaced:
        warnings.append(
            CategoryWarning(code=CategoryWarningCode.UNPLACED_TEAMS, team_names=unplaced)
        )

    if category.age is not None and category.age <= MIN_MATCHES_MAX_AGE:
        guaranteed_per_team = {
            team.name: max(guaranteed_per_stage_item[id_] for id_ in stage_items_per_team[team.id])
            for team in active_teams
            if team.id in stage_items_per_team
        }
        too_few = {
            name: count
            for name, count in guaranteed_per_team.items()
            if count < MIN_MATCHES_PER_TEAM
        }
        if too_few:
            warnings.append(
                CategoryWarning(
                    code=CategoryWarningCode.TOO_FEW_MATCHES,
                    minimum_matches=min(too_few.values()),
                    team_names=sorted(too_few),
                )
            )

    return warnings


def get_warnings_per_category(
    categories: list[Category],
    teams: list[FullTeamWithPlayers],
    stages: list[StageWithStageItems],
) -> dict[CategoryId, list[CategoryWarning]]:
    return {
        category.id: get_category_warnings(
            category,
            [team for team in teams if team.category_id == category.id],
            [stage for stage in stages if stage.category_id == category.id],
        )
        for category in categories
    }
