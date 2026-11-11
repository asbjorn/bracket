"""
Ordering teams in a group: by points, then by the tiebreakers of the ranking, in that order.
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import groupby
from typing import Literal

from bracket.logic.ranking.statistics import TeamStatistics
from bracket.models.db.match import MatchWithDetailsDefinitive
from bracket.models.db.ranking import Ranking, Tiebreaker
from bracket.utils.id_types import StageItemInputId

Criterion = Tiebreaker | Literal["POINTS"]


@dataclass(frozen=True)
class TiebreakerData:
    """What some tiebreakers need besides the matches: card points and drawn lots per team."""

    # Fair play: card points per input (fewer is better)
    card_points: dict[StageItemInputId, int] = field(default_factory=dict)
    # Drawing of lots entered by the organiser (lower is better)
    lot_numbers: dict[StageItemInputId, int] = field(default_factory=dict)
    # Seeds the random order of the lots that weren't entered (stable for the group)
    lots_seed: int = 0


def random_lot(seed: int, input_id: StageItemInputId) -> int:
    """A fixed random number per team and group: the drawn order doesn't change on reloads."""
    digest = hashlib.sha256(f"{seed}:{input_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def lots_values(
    input_ids: Sequence[StageItemInputId], data: TiebreakerData
) -> dict[StageItemInputId, Decimal]:
    """Higher is better: entered lot numbers first (lowest best), then the random order."""
    entered = [input_id for input_id in input_ids if input_id in data.lot_numbers]
    values: dict[StageItemInputId, Decimal] = {
        input_id: Decimal(2**64) + Decimal(1000 - data.lot_numbers[input_id])
        for input_id in entered
    }
    for input_id in input_ids:
        if input_id not in values:
            values[input_id] = Decimal(2**64 - 1 - random_lot(data.lots_seed, input_id))
    return values


def head_to_head_points(
    input_ids: Sequence[StageItemInputId],
    played_matches: Sequence[MatchWithDetailsDefinitive],
    ranking: Ranking,
) -> dict[StageItemInputId, Decimal]:
    """
    Points from the matches between the given teams only (a "mini table").
    """
    points = {input_id: Decimal("0") for input_id in input_ids}
    for match in played_matches:
        input1, input2 = match.stage_item_input1_id, match.stage_item_input2_id
        if input1 not in points or input2 not in points:
            continue

        score1, score2 = match.stage_item_input1_score, match.stage_item_input2_score
        if score1 == score2:
            points[input1] += ranking.draw_points
            points[input2] += ranking.draw_points
        else:
            winner, loser = (input1, input2) if score1 > score2 else (input2, input1)
            points[winner] += ranking.win_points
            points[loser] += ranking.loss_points
    return points


def criterion_values(  # pylint: disable=too-many-return-statements
    criterion: Criterion,
    input_ids: Sequence[StageItemInputId],
    stats: dict[StageItemInputId, TeamStatistics],
    played_matches: Sequence[MatchWithDetailsDefinitive],
    ranking: Ranking,
    data: TiebreakerData,
) -> dict[StageItemInputId, Decimal]:
    """The value of the criterion per team: higher is better."""
    match criterion:
        case "POINTS":
            return {input_id: stats[input_id].points for input_id in input_ids}
        case Tiebreaker.GOAL_DIFFERENCE:
            return {input_id: Decimal(stats[input_id].goal_difference) for input_id in input_ids}
        case Tiebreaker.GOALS_SCORED:
            return {input_id: Decimal(stats[input_id].goals_for) for input_id in input_ids}
        case Tiebreaker.HEAD_TO_HEAD:
            return head_to_head_points(input_ids, played_matches, ranking)
        case Tiebreaker.FAIR_PLAY:
            return {input_id: Decimal(-data.card_points.get(input_id, 0)) for input_id in input_ids}
        case Tiebreaker.LOTS:
            return lots_values(input_ids, data)


def order_tied_groups(
    input_ids: list[StageItemInputId],
    criteria: Sequence[Criterion],
    stats: dict[StageItemInputId, TeamStatistics],
    played_matches: Sequence[MatchWithDetailsDefinitive],
    ranking: Ranking,
    data: TiebreakerData,
) -> list[list[StageItemInputId]]:
    """
    Orders teams by the first criterion. Teams that are still equal are ordered by the next
    criteria, where head-to-head only looks at the matches between the teams that are still tied.
    Returns groups of teams that are equal on all criteria, best first.
    """
    if len(input_ids) < 2 or len(criteria) < 1:
        return [input_ids]

    values = criterion_values(criteria[0], input_ids, stats, played_matches, ranking, data)
    # `sorted` is stable, so teams with equal values keep their order
    ordered = sorted(input_ids, key=lambda input_id: values[input_id], reverse=True)
    return [
        subgroup
        for _, group in groupby(ordered, key=lambda input_id: values[input_id])
        for subgroup in order_tied_groups(
            list(group), criteria[1:], stats, played_matches, ranking, data
        )
    ]


def order_by_ranking(
    input_ids: list[StageItemInputId],
    stats: dict[StageItemInputId, TeamStatistics],
    played_matches: Sequence[MatchWithDetailsDefinitive],
    ranking: Ranking,
    *,
    use_tiebreakers: bool,
    data: TiebreakerData | None = None,
) -> list[StageItemInputId]:
    """
    Orders teams by points and then by the tiebreakers of the ranking. Teams that are equal on
    everything keep the given order (e.g. by slot).
    """
    criteria: list[Criterion] = ["POINTS", *(ranking.tiebreakers if use_tiebreakers else [])]
    groups = order_tied_groups(
        input_ids, criteria, stats, played_matches, ranking, data or TiebreakerData()
    )
    return [input_id for group in groups for input_id in group]
