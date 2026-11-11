"""
Group draw: teams are drawn into the free slots of the groups of a stage.

- Pots: pot by pot, the teams of a pot go to different groups (one team per pot per group) as
  long as there are enough groups. A pot with more teams than groups is drawn in rounds.
- Clubs: teams of the same club are kept in different groups where possible.
- Otherwise random, while filling the groups evenly.

Within a round every team goes to another group, so the best round is an assignment problem:
solved exactly with the Hungarian algorithm on these costs (most important first).
"""

import random
import re
from dataclasses import dataclass

from bracket.logic.scheduling.playoffs import min_cost_assignment

SAME_CLUB_COST = 1_000_000
SAME_POT_COST = 10_000
# Prefer the groups with the most free slots, so groups fill evenly
FULLER_GROUP_COST = 100
RANDOM_COST = 100  # Below every other cost: only decides between equally good groups

TRAILING_NUMBER = re.compile(r"\s+\d+$")


def club_of(team_name: str, club_name: str | None) -> str:
    """The club of a team: given, or its name without a trailing number ("Brann 2" -> "Brann")."""
    club = club_name if club_name else TRAILING_NUMBER.sub("", team_name.strip())
    return club.strip().casefold()


@dataclass(frozen=True)
class DrawTeam:
    id: int
    club: str


@dataclass
class DrawGroup:
    free_slots: list[int]  # Ids of the empty slots (stage item inputs), in order
    clubs: list[str]  # Clubs of the teams in the group
    pots: list[int]  # Pots of the teams drawn into the group


@dataclass(frozen=True)
class Placement:
    team_id: int
    group_index: int
    slot_id: int


def group_cost(team: DrawTeam, pot: int, group: DrawGroup, most_free: int) -> int:
    return (
        SAME_CLUB_COST * group.clubs.count(team.club)
        + SAME_POT_COST * group.pots.count(pot)
        + FULLER_GROUP_COST * (most_free - len(group.free_slots))
    )


def draw_round(
    teams: list[DrawTeam], pot: int, groups: list[DrawGroup], rng: random.Random
) -> list[Placement]:
    """Draws at most one team into every group that has a free slot."""
    open_groups = [index for index, group in enumerate(groups) if group.free_slots]
    assert len(teams) <= len(open_groups)
    most_free = max(len(groups[index].free_slots) for index in open_groups)
    cost = [
        [
            group_cost(team, pot, groups[index], most_free) + rng.randrange(RANDOM_COST)
            for index in open_groups
        ]
        for team in teams
    ]
    # Square matrix: rows without a team cost nothing
    cost += [[0] * len(open_groups) for _ in range(len(open_groups) - len(teams))]
    columns = min_cost_assignment(cost)

    placements = []
    for team, column in zip(teams, columns, strict=False):
        group_index = open_groups[column]
        group = groups[group_index]
        placements.append(Placement(team.id, group_index, group.free_slots.pop(0)))
        group.clubs.append(team.club)
        group.pots.append(pot)
    return placements


def draw_groups(
    pots: list[list[DrawTeam]], groups: list[DrawGroup], rng: random.Random
) -> list[Placement]:
    """
    Places the teams of all pots, in the order they are drawn (pot by pot, in random order
    within a pot), so the draw can be revealed team by team. `groups` are updated.
    """
    if sum(len(pot) for pot in pots) > sum(len(group.free_slots) for group in groups):
        raise ValueError("There are more teams than free places in the groups")

    placements: list[Placement] = []
    for pot_index, pot in enumerate(pots):
        remaining = list(pot)
        rng.shuffle(remaining)
        while remaining:
            open_groups = sum(1 for group in groups if group.free_slots)
            round_teams, remaining = remaining[:open_groups], remaining[open_groups:]
            placements += draw_round(round_teams, pot_index, groups, rng)
    return placements
