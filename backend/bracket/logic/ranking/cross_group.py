"""
Comparing teams at the same placing across groups, e.g. to find the best third placed teams.

Groups can have different sizes, so teams are compared per match played: points, then goal
difference, then goals scored. Teams that are still equal keep the order of their groups (by
name).
"""

from decimal import Decimal

from bracket.logic.ranking.statistics import TeamStatistics
from bracket.models.db.util import StageWithStageItems
from bracket.utils.id_types import StageItemId, StageItemInputId

StageItemXTeamRanking = dict[StageItemId, list[tuple[StageItemInputId, TeamStatistics]]]


def per_match(value: Decimal | int, played: int) -> Decimal:
    return Decimal(value) / played if played > 0 else Decimal("0")


def rank_teams_at_placing(
    stage: StageWithStageItems, placing: int, rankings: StageItemXTeamRanking
) -> list[StageItemInputId]:
    """
    The inputs that finished at `placing` (1 = winner) in the groups of the stage, best first.
    Groups with fewer teams than `placing` don't take part.
    """
    candidates: list[tuple[StageItemInputId, TeamStatistics]] = []
    for group in sorted(stage.stage_items, key=lambda group: group.name):
        ranking = rankings.get(group.id, [])
        if len(ranking) >= placing:
            candidates.append(ranking[placing - 1])

    def key(candidate: tuple[StageItemInputId, TeamStatistics]) -> tuple[Decimal, ...]:
        stats = candidate[1]
        played = stats.wins + stats.draws + stats.losses
        return (
            per_match(stats.points, played),
            per_match(stats.goal_difference, played),
            per_match(stats.goals_for, played),
        )

    # `sorted` is stable, so equal teams keep the order of their groups
    return [input_id for input_id, _ in sorted(candidates, key=key, reverse=True)]
