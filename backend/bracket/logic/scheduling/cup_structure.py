"""
The structure of a class in a cup: how teams are split into groups and which placings go to
which playoff. Used by the capacity calculator and the cup setup wizard.
"""

import math
from enum import StrEnum


class PlayoffPreset(StrEnum):
    """No playoffs, one playoff for everyone, or A/B (/C) playoffs split by placing."""

    NONE = "NONE"
    A = "A"
    AB = "AB"
    ABC = "ABC"

    @property
    def playoff_count(self) -> int:
        return {"NONE": 0, "A": 1, "AB": 2, "ABC": 3}[self.value]


PLAYOFF_NAMES = ["A", "B", "C"]


def split_into_groups(team_count: int, group_size: int) -> list[int]:
    """
    The sizes of the groups when `team_count` teams play in groups of (about) `group_size`:
    as few groups as possible, sizes differ by at most one, larger groups first.
    E.g. 10 teams in groups of 4: [4, 3, 3].
    """
    group_count = max(1, math.ceil(team_count / group_size))
    base, extra = divmod(team_count, group_count)
    return [base + 1 if index < extra else base for index in range(group_count)]


def split_placings(group_size: int, playoff_count: int) -> list[list[int]]:
    """
    Placings 1..group_size split into `playoff_count` playoffs of (almost) equal size, best
    first. E.g. groups of 4 into A and B: [[1, 2], [3, 4]].
    """
    result: list[list[int]] = []
    next_placing = 1
    for index in range(playoff_count):
        size = math.ceil((group_size - next_placing + 1) / (playoff_count - index))
        result.append(list(range(next_placing, next_placing + size)))
        next_placing += size
    return [placings for placings in result if placings]
