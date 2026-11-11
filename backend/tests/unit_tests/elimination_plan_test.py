import pytest

from bracket.logic.scheduling.elimination import (
    FromInput,
    FromMatch,
    get_bye_pairs,
    plan_single_elimination,
)


def winner(round_index: int, match_index: int) -> FromMatch:
    return FromMatch("winner", round_index, match_index)


def test_power_of_two_has_no_byes_and_pairs_slots_in_order() -> None:
    plan = plan_single_elimination(4)
    assert plan == [
        [(FromInput(0), FromInput(1)), (FromInput(2), FromInput(3))],
        [(winner(0, 0), winner(0, 1))],
    ]


def test_six_teams_byes_are_spread() -> None:
    """
    6 teams in a bracket of 8: two byes, in different halves, so the teams with a bye don't
    meet each other in their first match.
    """
    assert get_bye_pairs(6) == {0, 2}
    plan = plan_single_elimination(6)
    assert plan == [
        [(FromInput(1), FromInput(2)), (FromInput(4), FromInput(5))],
        [(FromInput(0), winner(0, 0)), (FromInput(3), winner(0, 1))],
        [(winner(1, 0), winner(1, 1))],
    ]


def test_three_teams() -> None:
    assert plan_single_elimination(3) == [
        [(FromInput(1), FromInput(2))],
        [(FromInput(0), winner(0, 0))],
    ]


@pytest.mark.parametrize("team_count", range(2, 65))
def test_every_team_count_gives_a_valid_bracket(team_count: int) -> None:
    """
    Every team plays, there is one final, and the number of matches is team_count - 1
    (every match eliminates one team).
    """
    plan = plan_single_elimination(team_count)
    matches = [match for round_ in plan for match in round_]
    slots = sorted(s.slot_index for m in matches for s in m if isinstance(s, FromInput))

    assert slots == list(range(team_count))
    assert len(plan[-1]) == 1
    assert len(matches) == team_count - 1
    # No team gets a bye beyond the first round: second round onward only has winners and
    # teams with a bye
    for round_index, round_ in enumerate(plan[2:], start=2):
        for match in round_:
            assert all(isinstance(s, FromMatch) and s.round_index < round_index for s in match)


def test_third_place_match() -> None:
    plan = plan_single_elimination(8, third_place_match=True)
    assert plan[-1] == [
        (winner(1, 0), winner(1, 1)),
        (FromMatch("loser", 1, 0), FromMatch("loser", 1, 1)),
    ]

    with pytest.raises(ValueError, match="at least 4 teams"):
        plan_single_elimination(3, third_place_match=True)
