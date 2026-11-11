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
from functools import partial
from itertools import combinations, permutations

from bracket.logic.scheduling.elimination import (
    get_bracket_size,
    get_seed_per_slot,
    standard_seed_order,
)

# Above this number of groups, finding the best order of groups would take too long, so the
# groups keep their order.
MAX_GROUPS_TO_OPTIMIZE = 8


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


def same_group_cost(seeds: list[Qualifier], bracket_size: int) -> int:
    """
    Penalty for teams of the same group that can meet early; meeting in an earlier round costs
    more than any number of meetings in later rounds.
    """
    position_of_seed = {seed: index for index, seed in enumerate(standard_seed_order(bracket_size))}
    round_count = int(math.log2(bracket_size))
    # Larger than the number of pairs, so one earlier meeting outweighs all later ones
    base = bracket_size**2
    cost = 0
    for (seed1, team1), (seed2, team2) in combinations(enumerate(seeds, start=1), 2):
        if team1.group_index == team2.group_index:
            meeting_round = first_possible_meeting_round(
                position_of_seed[seed1], position_of_seed[seed2]
            )
            cost += base ** (round_count - meeting_round)
    return cost


def order_cost(
    order: tuple[Qualifier, ...], *, seeded_so_far: list[Qualifier], bracket_size: int
) -> int:
    return same_group_cost(seeded_so_far + list(order), bracket_size)


def seed_qualifiers(qualifiers: list[Qualifier]) -> list[Qualifier]:
    """
    Orders the qualifiers by seed (index 0 = seed 1): by placing, and within a placing by the
    order of groups that keeps teams of the same group apart the longest.
    """
    bracket_size = get_bracket_size(len(qualifiers))
    seeds: list[Qualifier] = []
    for placing in sorted({q.placing for q in qualifiers}):
        same_placing = sorted(
            (q for q in qualifiers if q.placing == placing), key=lambda q: q.group_index
        )
        if len(same_placing) > MAX_GROUPS_TO_OPTIMIZE:
            seeds += same_placing
            continue
        # `min` keeps the first best order, so ties are resolved by the order of the groups
        seeded_so_far = list(seeds)
        best = min(
            permutations(same_placing),
            key=partial(order_cost, seeded_so_far=seeded_so_far, bracket_size=bracket_size),
        )
        seeds += best
    return seeds


def get_qualifiers_per_slot(qualifiers: list[Qualifier]) -> list[Qualifier]:
    """
    The qualifier for each slot of the knockout bracket (slot order), following standard seeding.
    """
    seeds = seed_qualifiers(qualifiers)
    return [seeds[seed - 1] for seed in get_seed_per_slot(len(qualifiers))]
