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
