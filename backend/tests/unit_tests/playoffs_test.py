from itertools import combinations

import pytest

from bracket.logic.scheduling.elimination import FromInput, Source, plan_single_elimination
from bracket.logic.scheduling.playoffs import (
    Qualifier,
    first_possible_meeting_round,
    get_qualifiers_per_slot,
)

A, B, C, D = 0, 1, 2, 3


def slot_of(source: Source) -> int:
    assert isinstance(source, FromInput), "The first round only has teams from slots"
    return source.slot_index


def first_round_pairs(team_count: int, slots: list[Qualifier]) -> list[tuple[str, str]]:
    def label(q: Qualifier) -> str:
        return f"{q.placing}{'ABCDEFGH'[q.group_index]}"

    return [
        (label(slots[slot_of(m[0])]), label(slots[slot_of(m[1])]))
        for m in plan_single_elimination(team_count)[0]
    ]


def test_two_groups_cross_semifinals() -> None:
    qualifiers = [Qualifier(g, p) for g in (A, B) for p in (1, 2)]
    slots = get_qualifiers_per_slot(qualifiers)
    assert first_round_pairs(4, slots) == [("1A", "2B"), ("1B", "2A")]


def test_four_groups_quarterfinals() -> None:
    """
    Winners play runners-up of other groups, and teams of the same group are in different
    halves of the bracket, so they can only meet in the final.
    """
    qualifiers = [Qualifier(g, p) for g in (A, B, C, D) for p in (1, 2)]
    slots = get_qualifiers_per_slot(qualifiers)
    pairs = first_round_pairs(8, slots)

    assert all(pair[0][0] == "1" and pair[1][0] == "2" for pair in pairs)
    for index1, index2 in combinations(range(8), 2):
        if slots[index1].group_index == slots[index2].group_index:
            assert first_possible_meeting_round(index1, index2) == 3, (slots[index1], slots[index2])


def test_same_group_never_meets_in_first_match_with_byes() -> None:
    """
    3 groups, top 2: 6 teams, the two best group winners get a bye.
    """
    qualifiers = [Qualifier(g, p) for g in (A, B, C) for p in (1, 2)]
    slots = get_qualifiers_per_slot(qualifiers)
    plan = plan_single_elimination(6)
    first_round = plan[0]
    for match in first_round:
        team1, team2 = (slots[slot_of(source)] for source in match)
        assert team1.group_index != team2.group_index
    # Teams with a bye are group winners
    bye_slots = set(range(6)) - {slot_of(source) for m in first_round for source in m}
    assert {slots[slot].placing for slot in bye_slots} == {1}


@pytest.mark.parametrize(("position1", "position2", "expected"), [(0, 1, 1), (0, 3, 2), (0, 7, 3)])
def test_first_possible_meeting_round(position1: int, position2: int, expected: int) -> None:
    assert first_possible_meeting_round(position1, position2) == expected
