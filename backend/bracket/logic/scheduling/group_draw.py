"""
Group draw: teams are drawn into the free slots of the groups of a stage.

- Pots: pot by pot, the teams of a pot go to different groups (one team per pot per group) as
  long as there are enough groups. A pot with more teams than groups is drawn in rounds.
- Clubs: teams of the same club are kept in different groups where possible.
- Otherwise random, while filling the groups evenly.

Within a round every team goes to another group, so the best round is an assignment problem:
solved exactly with the Hungarian algorithm on these costs (most important first).
"""

import itertools
import random
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

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


def club_name_of(club_id: int | None, club_names: Mapping[Any, str]) -> str | None:
    """The name of a team's club, if it has one."""
    return None if club_id is None else club_names.get(club_id)


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


RESTARTS = 20


def pairs(values: list[Any]) -> int:
    return sum(values.count(value) * (values.count(value) - 1) // 2 for value in set(values))


def group_clashes(group: DrawGroup) -> tuple[int, int]:
    """Pairs of teams of the same club, and of the same pot, in the group."""
    return pairs(group.clubs), pairs(group.pots)


def clashes(groups: list[DrawGroup]) -> tuple[int, int]:
    """All same-club and same-pot pairs (lower is better, clubs first)."""
    per_group = [group_clashes(group) for group in groups]
    return sum(c for c, _ in per_group), sum(p for _, p in per_group)


def greedy_draw(
    pots: list[list[DrawTeam]], groups: list[DrawGroup], rng: random.Random
) -> list[Placement]:
    """Pot by pot, in rounds of at most one team per group, each round solved exactly."""
    placements: list[Placement] = []
    for pot_index, pot in enumerate(pots):
        remaining = list(pot)
        rng.shuffle(remaining)
        while remaining:
            open_groups = sum(1 for group in groups if group.free_slots)
            round_teams, remaining = remaining[:open_groups], remaining[open_groups:]
            placements += draw_round(round_teams, pot_index, groups, rng)
    return placements


def improve_by_swaps(
    placements: list[Placement],
    groups: list[DrawGroup],
    team_by_id: dict[int, tuple[DrawTeam, int]],
) -> list[Placement]:
    """
    Swaps two drawn teams between groups while that lowers the clashes (clubs first, then
    pots). Rounds are solved one at a time, so a team drawn early can block a better
    placement for a team of the same club drawn later; swapping repairs that.
    """
    placements = list(placements)
    improved = True
    while improved:
        improved = False
        for i, j in itertools.combinations(range(len(placements)), 2):
            if try_swap(placements, i, j, groups, team_by_id):
                improved = True
    return placements


def try_swap(
    placements: list[Placement],
    i: int,
    j: int,
    groups: list[DrawGroup],
    team_by_id: dict[int, tuple[DrawTeam, int]],
) -> bool:
    """Swaps placements i and j if that lowers the clashes of their two groups."""
    first, second = placements[i], placements[j]
    if first.group_index == second.group_index:
        return False
    team1, pot1 = team_by_id[first.team_id]
    team2, pot2 = team_by_id[second.team_id]
    if team1.club == team2.club and pot1 == pot2:
        return False  # Swapping changes nothing
    touched = [groups[first.group_index], groups[second.group_index]]
    before = tuple(map(sum, zip(*map(group_clashes, touched), strict=True)))
    swap_teams(groups, first, second, team_by_id)
    after = tuple(map(sum, zip(*map(group_clashes, touched), strict=True)))
    if after < before:
        placements[i] = Placement(first.team_id, second.group_index, second.slot_id)
        placements[j] = Placement(second.team_id, first.group_index, first.slot_id)
        return True
    # Undo: the teams are now in each other's groups
    swap_teams(
        groups,
        Placement(first.team_id, second.group_index, second.slot_id),
        Placement(second.team_id, first.group_index, first.slot_id),
        team_by_id,
    )
    return False


def swap_teams(
    groups: list[DrawGroup],
    first: Placement,
    second: Placement,
    team_by_id: dict[int, tuple[DrawTeam, int]],
) -> None:
    """Moves `first`'s team to `second`'s group and the other way around (clubs and pots)."""
    team1, pot1 = team_by_id[first.team_id]
    team2, pot2 = team_by_id[second.team_id]
    group1, group2 = groups[first.group_index], groups[second.group_index]
    group1.clubs.remove(team1.club)
    group1.pots.remove(pot1)
    group2.clubs.remove(team2.club)
    group2.pots.remove(pot2)
    group1.clubs.append(team2.club)
    group1.pots.append(pot2)
    group2.clubs.append(team1.club)
    group2.pots.append(pot1)


def draw_groups(
    pots: list[list[DrawTeam]], groups: list[DrawGroup], rng: random.Random
) -> list[Placement]:
    """
    Places the teams of all pots, in the order they are drawn (pot by pot, in random order
    within a pot), so the draw can be revealed team by team. `groups` are updated.

    Several random draws are improved by swapping teams, and the one with the fewest clashes
    (same club in a group first, then same pot) is kept.
    """
    if sum(len(pot) for pot in pots) > sum(len(group.free_slots) for group in groups):
        raise ValueError("There are more teams than free places in the groups")

    team_by_id = {team.id: (team, pot_index) for pot_index, pot in enumerate(pots) for team in pot}
    best_score: tuple[int, int] | None = None
    best_placements: list[Placement] = []
    best_groups: list[DrawGroup] = []
    for _ in range(RESTARTS):
        attempt = [
            DrawGroup(list(group.free_slots), list(group.clubs), list(group.pots))
            for group in groups
        ]
        placements = improve_by_swaps(greedy_draw(pots, attempt, rng), attempt, team_by_id)
        score = clashes(attempt)
        if best_score is None or score < best_score:
            best_score, best_placements, best_groups = score, placements, attempt
        if score == (0, 0):
            break

    result = best_groups
    for group, drawn in zip(groups, result, strict=True):
        group.free_slots[:] = drawn.free_slots
        group.clubs[:] = drawn.clubs
        group.pots[:] = drawn.pots
    return best_placements
