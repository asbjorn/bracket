"""
Creating playoffs (sluttspill) from a group stage, e.g. an A playoff for the two best teams of
every group and a B playoff for the others.

Teams are seeded by placing (all group winners first, then all runners-up, etc.) and placed in a
knockout bracket with standard seeding. Within each placing, the order of the groups is chosen
such that teams from the same group meet as late as possible: with two groups that gives the
classic cross semifinals 1A-2B and 1B-2A.
"""

import math
from dataclasses import dataclass

from bracket.logic.scheduling.elimination import (
    get_bracket_size,
    get_seed_per_slot,
    standard_seed_order,
)


@dataclass(frozen=True)
class Qualifier:
    """The team at `placing` (1 = winner) of the group with index `group_index`."""

    group_index: int
    placing: int


def first_possible_meeting_round(position1: int, position2: int) -> int:
    """
    The round (1 = first round) in which teams at these positions of a full bracket can meet.
    """
    return (position1 ^ position2).bit_length()


def meeting_cost(position1: int, position2: int, bracket_size: int) -> int:
    """
    Penalty for two teams of the same group at these positions. Meeting one round earlier costs
    more than all possible meetings in later rounds together (the base exceeds the number of
    pairs).
    """
    round_count = int(math.log2(bracket_size))
    base = bracket_size**2
    exponent = round_count - first_possible_meeting_round(position1, position2)
    return int(base**exponent)


def assign_along_path(row_of_column: list[int], way: list[int], column: int) -> None:
    """
    Part of `min_cost_assignment`: shifts the assignments along the found augmenting path.
    """
    while column != 0:
        previous = way[column]
        row_of_column[column] = row_of_column[previous]
        column = previous


def min_cost_assignment(cost: list[list[int]]) -> list[int]:
    """
    Hungarian algorithm, O(n^3): for a square cost matrix, returns for every row the column it's
    assigned to, such that every column is used once and the total cost is minimal.
    """
    n = len(cost)
    infinity = sum(sum(row) for row in cost) + 1
    u = [0] * (n + 1)
    v = [0] * (n + 1)
    row_of_column = [0] * (n + 1)
    way = [0] * (n + 1)
    for row in range(1, n + 1):
        row_of_column[0] = row
        column0 = 0
        min_value = [infinity] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[column0] = True
            row0 = row_of_column[column0]
            delta = infinity
            column1 = 0
            for column in range(1, n + 1):
                if not used[column]:
                    reduced = cost[row0 - 1][column - 1] - u[row0] - v[column]
                    if reduced < min_value[column]:
                        min_value[column] = reduced
                        way[column] = column0
                    if min_value[column] < delta:
                        delta = min_value[column]
                        column1 = column
            for column in range(n + 1):
                if used[column]:
                    u[row_of_column[column]] += delta
                    v[column] -= delta
                else:
                    min_value[column] -= delta
            column0 = column1
            if row_of_column[column0] == 0:
                break
        assign_along_path(row_of_column, way, column0)

    assignment = [0] * n
    for column in range(1, n + 1):
        assignment[row_of_column[column] - 1] = column - 1
    return assignment


def seed_qualifiers(qualifiers: list[Qualifier]) -> list[Qualifier]:
    """
    Orders the qualifiers by seed (index 0 = seed 1): by placing, and within a placing by the
    order of groups that keeps teams of the same group apart the longest.

    Within a placing every group has one team, so the penalty of putting a group at a seed only
    depends on the teams of that group seeded before. That makes it an assignment problem, which
    is solved exactly in polynomial time.
    """
    bracket_size = get_bracket_size(len(qualifiers))
    position_of_seed = {seed: index for index, seed in enumerate(standard_seed_order(bracket_size))}
    seeds: list[Qualifier] = []
    for placing in sorted({q.placing for q in qualifiers}):
        same_placing = sorted(
            (q for q in qualifiers if q.placing == placing), key=lambda q: q.group_index
        )
        count = len(same_placing)
        first_seed = len(seeds) + 1
        # Breaking ties: keep the order of the groups. This term is always smaller than one
        # unit of the main cost.
        scale = count * count + 1
        cost = [
            [
                scale
                * sum(
                    meeting_cost(
                        position_of_seed[first_seed + column],
                        position_of_seed[seed],
                        bracket_size,
                    )
                    for seed, team in enumerate(seeds, start=1)
                    if team.group_index == qualifier.group_index
                )
                + abs(row - column)
                for column in range(count)
            ]
            for row, qualifier in enumerate(same_placing)
        ]
        ordered: list[Qualifier | None] = [None] * count
        for row, column in enumerate(min_cost_assignment(cost)):
            ordered[column] = same_placing[row]
        seeds += [qualifier for qualifier in ordered if qualifier is not None]
    return seeds


def get_qualifiers_per_slot(qualifiers: list[Qualifier]) -> list[Qualifier]:
    """
    The qualifier for each slot of the knockout bracket (slot order), following standard seeding.
    """
    seeds = seed_qualifiers(qualifiers)
    return [seeds[seed - 1] for seed in get_seed_per_slot(len(qualifiers))]
