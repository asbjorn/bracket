import itertools
import random
from collections import Counter

import pytest

from bracket.logic.scheduling.group_draw import (
    DrawGroup,
    DrawTeam,
    Placement,
    club_of,
    draw_groups,
)


def empty_groups(*sizes: int) -> list[DrawGroup]:
    return [
        DrawGroup(free_slots=[100 * index + slot for slot in range(size)], clubs=[], pots=[])
        for index, size in enumerate(sizes)
    ]


def teams(start: int, count: int, club: str | None = None) -> list[DrawTeam]:
    return [DrawTeam(id, club or f"club{id}") for id in range(start, start + count)]


def groups_of(placements: list[Placement]) -> dict[int, int]:
    return {placement.team_id: placement.group_index for placement in placements}


def test_club_of() -> None:
    assert club_of("Brann 2", None) == "brann"
    assert club_of("Brann", None) == "brann"
    assert club_of("Fana IL 11", None) == "fana il"
    assert club_of("Brann Rød", "Brann") == "brann"
    assert club_of("Lyn 1", "") == "lyn"


def test_one_team_per_pot_per_group() -> None:
    for seed in range(20):
        pots = [teams(10 * pot, 4) for pot in range(4)]
        groups = empty_groups(4, 4, 4, 4)
        placements = draw_groups(pots, groups, random.Random(seed))

        assert len(placements) == 16
        assert len({placement.slot_id for placement in placements}) == 16
        group_of = groups_of(placements)
        for pot in pots:
            assert sorted(group_of[team.id] for team in pot) == [0, 1, 2, 3]
        assert all(not group.free_slots for group in groups)


def test_same_club_apart() -> None:
    for seed in range(20):
        brann = teams(1, 4, "brann")
        others = teams(10, 12)
        placements = draw_groups([brann + others], empty_groups(4, 4, 4, 4), random.Random(seed))
        group_of = groups_of(placements)
        assert sorted(group_of[team.id] for team in brann) == [0, 1, 2, 3]


def test_same_club_spread_when_unavoidable() -> None:
    """Five teams of one club in four groups: one group gets two, not three."""
    brann = teams(1, 5, "brann")
    placements = draw_groups([brann, teams(10, 11)], empty_groups(4, 4, 4, 4), random.Random(3))
    group_of = groups_of(placements)
    assert sorted(Counter(group_of[team.id] for team in brann).values()) == [1, 1, 1, 2]


def test_club_beats_pot() -> None:
    """Clubs apart matters more than one team per pot per group."""
    groups = empty_groups(2, 2)
    # Group 0 already has a Brann team
    groups[0] = DrawGroup(free_slots=[1], clubs=["brann"], pots=[])
    pots = [[DrawTeam(1, "brann"), DrawTeam(2, "lyn")]]
    placements = draw_groups(pots, groups, random.Random(0))
    assert groups_of(placements) == {1: 1, 2: 0}


def test_uneven_groups_and_existing_teams() -> None:
    placements = draw_groups([teams(1, 10)], empty_groups(4, 3, 3), random.Random(1))
    assert Counter(groups_of(placements).values()) == {0: 4, 1: 3, 2: 3}

    groups = empty_groups(4, 4)
    groups[0].free_slots = groups[0].free_slots[:1]  # Three places already taken
    placements = draw_groups([teams(1, 5)], groups, random.Random(1))
    assert Counter(groups_of(placements).values()) == {0: 1, 1: 4}


def test_random_but_reproducible() -> None:
    def draw(seed: int) -> list[Placement]:
        return draw_groups([teams(1, 16)], empty_groups(4, 4, 4, 4), random.Random(seed))

    assert draw(1) == draw(1)
    assert len({tuple(draw(seed)) for seed in range(10)}) > 1


def test_too_many_teams() -> None:
    with pytest.raises(ValueError, match="more teams than free places"):
        draw_groups([teams(1, 9)], empty_groups(4, 4), random.Random(0))


def test_clubs_apart_when_pot_is_larger_than_groups() -> None:
    """
    Regression (browser test, J13): 2 pots of 4 teams, 2 groups of 4. Two clubs each have one
    team in each pot; solving pot rounds one at a time put both teams of a club together.
    """
    gneist = [DrawTeam(1, "gneist"), DrawTeam(5, "gneist")]
    viking = [DrawTeam(2, "viking"), DrawTeam(6, "viking")]
    pots = [[gneist[0], viking[0], DrawTeam(3, "a"), DrawTeam(4, "b")]]
    pots.append([gneist[1], viking[1], DrawTeam(7, "c"), DrawTeam(8, "d")])
    for seed in range(50):
        groups = empty_groups(4, 4)
        group_of = groups_of(draw_groups(pots, groups, random.Random(seed)))
        assert group_of[1] != group_of[5], seed
        assert group_of[2] != group_of[6], seed
        # Still two teams of each pot per group
        assert sorted(Counter(group_of[t.id] for t in pots[0]).values()) == [2, 2]


def best_possible_club_clashes(all_teams: list[DrawTeam], sizes: list[int]) -> int:
    """Brute force: the fewest same-club pairs over every split of the teams into groups."""
    best = None
    for assignment in itertools.product(range(len(sizes)), repeat=len(all_teams)):
        if [assignment.count(g) for g in range(len(sizes))] != sizes:
            continue
        pairs = 0
        for g in range(len(sizes)):
            clubs = [team.club for team, a in zip(all_teams, assignment, strict=True) if a == g]
            pairs += sum(clubs.count(c) * (clubs.count(c) - 1) // 2 for c in set(clubs))
        best = pairs if best is None else min(best, pairs)
    assert best is not None
    return best


def test_club_separation_is_optimal_on_small_cases() -> None:
    rng = random.Random(11)
    for case in range(150):
        sizes = rng.choice([[3, 3], [4, 4], [3, 3, 2], [4, 3], [2, 2, 2]])
        count = sum(sizes)
        drawn_teams = [DrawTeam(i, rng.choice("abcd")) for i in range(count)]
        pot_count = rng.choice([1, 2])
        pots = [drawn_teams[i::pot_count] for i in range(pot_count)]
        groups = empty_groups(*sizes)
        draw_groups(pots, groups, random.Random(case))
        drawn = sum(
            g.clubs.count(c) * (g.clubs.count(c) - 1) // 2 for g in groups for c in set(g.clubs)
        )
        assert drawn == best_possible_club_clashes(drawn_teams, sizes), case
