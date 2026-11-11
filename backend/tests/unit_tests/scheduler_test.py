from datetime import timedelta
from zoneinfo import ZoneInfo

from heliclockter import datetime_utc

from bracket.logic.planning.scheduler import (
    CourtToPlan,
    Dependency,
    MatchToPlan,
    Window,
    determine_shortfall,
    schedule_matches,
    window_start_for,
)
from bracket.logic.scheduling.round_robin import get_round_robin_combinations
from bracket.models.db.game_format import GameFormat
from bracket.utils.id_types import CourtId, MatchId

DAY = datetime_utc(2026, 6, 13, tzinfo=ZoneInfo("UTC"))


def at(hour: int, minute: int = 0) -> datetime_utc:
    return DAY + timedelta(hours=hour, minutes=minute)


def group_matches(
    group: str, team_count: int, first_id: int, *, duration: int = 8, margin: int = 3
) -> list[MatchToPlan]:
    """Round robin matches of a group, with priority (stage 0, round, group)."""
    matches: list[MatchToPlan] = []
    for round_index, round_ in enumerate(get_round_robin_combinations(team_count)):
        for team1, team2 in round_:
            if team1 < team_count and team2 < team_count:
                matches.append(
                    MatchToPlan(
                        id=MatchId(first_id + len(matches)),
                        duration_minutes=duration,
                        margin_minutes=margin,
                        teams=frozenset({f"{group}{team1}", f"{group}{team2}"}),
                        priority=(0, round_index, ord(group)),
                    )
                )
    return matches


def knockout_match(
    match_id: int, dependencies: list[MatchId], delay: int, *, priority: tuple[int, ...]
) -> MatchToPlan:
    return MatchToPlan(
        id=MatchId(match_id),
        duration_minutes=8,
        margin_minutes=3,
        teams=frozenset({f"m{match_id}a", f"m{match_id}b"}),
        dependencies=tuple(Dependency(d, delay) for d in dependencies),
        priority=priority,
    )


def areacopa_indoor_matches() -> list[MatchToPlan]:
    """
    AreaCopa example: 8 teams in 2 groups of 4, semifinals 1A-2B and 1B-2A, final.
    The semifinals wait for the whole group stage plus a 5 minute buffer.
    """
    groups = group_matches("A", 4, 1) + group_matches("B", 4, 101)
    group_ids = [match.id for match in groups]
    semi1 = knockout_match(201, group_ids, 5, priority=(1, 0, 0))
    semi2 = knockout_match(202, group_ids, 5, priority=(1, 0, 1))
    final = knockout_match(203, [semi1.id, semi2.id], 0, priority=(1, 1, 0))
    return [*groups, semi1, semi2, final]


def test_areacopa_indoor_example_timeline() -> None:
    matches = areacopa_indoor_matches()
    result = schedule_matches(matches, [CourtToPlan(CourtId(1))], [Window(at(14), at(17))])

    assert result.fits
    starts = sorted(a.start for a in result.assignments.values())
    # Group matches every 11 minutes from 14:00, the 12th at 16:01
    assert starts[:12] == [at(14) + timedelta(minutes=11 * i) for i in range(12)]
    assert result.assignments[MatchId(201)].start == at(16, 17)
    assert result.assignments[MatchId(202)].start == at(16, 28)
    assert result.assignments[MatchId(203)].start == at(16, 39)


def test_no_team_plays_twice_in_a_row() -> None:
    """
    Groups alternate on the court, so teams always have a match off in between.
    """
    matches = areacopa_indoor_matches()[:12]
    result = schedule_matches(matches, [CourtToPlan(CourtId(1))], [Window(at(14), at(17))])
    by_start = sorted(matches, key=lambda m: result.assignments[m.id].start)
    for previous, current in zip(by_start, by_start[1:], strict=False):
        assert not previous.teams & current.teams, (previous.teams, current.teams)


def test_rest_between_matches_of_a_team() -> None:
    match1 = MatchToPlan(MatchId(1), 10, 0, frozenset({"A", "B"}), rest_minutes=20, priority=(0,))
    match2 = MatchToPlan(MatchId(2), 10, 0, frozenset({"A", "C"}), rest_minutes=20, priority=(1,))
    result = schedule_matches(
        [match1, match2],
        [CourtToPlan(CourtId(1)), CourtToPlan(CourtId(2))],
        [Window(at(9), at(12))],
    )
    assert result.assignments[MatchId(1)].start == at(9)
    # Team A plays until 9:10 and rests 20 minutes
    assert result.assignments[MatchId(2)].start == at(9, 30)


def test_matches_only_on_courts_of_their_format() -> None:
    small = MatchToPlan(MatchId(1), 10, 0, frozenset({"A", "B"}), game_format=GameFormat("5v5"))
    big = MatchToPlan(MatchId(2), 10, 0, frozenset({"C", "D"}), game_format=GameFormat("7v7"))
    courts = [CourtToPlan(CourtId(1), GameFormat("5v5")), CourtToPlan(CourtId(2), None)]
    result = schedule_matches([small, big], courts, [Window(at(9), at(10))])
    assert result.assignments[MatchId(1)].court_id == CourtId(1)
    # Only the court without a format fits 7v7
    assert result.assignments[MatchId(2)].court_id == CourtId(2)


def test_lunch_break_is_a_gap_between_windows() -> None:
    matches = [
        MatchToPlan(MatchId(i), 50, 0, frozenset({f"T{i}", f"U{i}"}), priority=(i,))
        for i in range(3)
    ]
    result = schedule_matches(
        matches, [CourtToPlan(CourtId(1))], [Window(at(10), at(12)), Window(at(13), at(15))]
    )
    # Two matches fit before lunch (10:00 and 10:50), the third starts after lunch
    assert [result.assignments[MatchId(i)].start for i in range(3)] == [
        at(10),
        at(10, 50),
        at(13),
    ]


def test_fixed_matches_keep_their_place() -> None:
    played = MatchToPlan(
        MatchId(1),
        10,
        0,
        frozenset({"A", "B"}),
        fixed_court_id=CourtId(1),
        fixed_start=at(9),
    )
    other = MatchToPlan(MatchId(2), 10, 0, frozenset({"C", "D"}))
    result = schedule_matches([played, other], [CourtToPlan(CourtId(1))], [Window(at(9), at(10))])
    assert result.assignments[MatchId(1)].start == at(9)
    assert result.assignments[MatchId(2)].start == at(9, 10)


def test_shortfall_courts_and_time() -> None:
    """
    The AreaCopa example doesn't fit in 14:00-16:00 on one court. With a second court it fits;
    on one court it needs until 16:47 (final 16:39 + 8 minutes), so 60 more minutes in steps
    of 15.
    """
    matches = areacopa_indoor_matches()
    courts = [CourtToPlan(CourtId(1))]
    windows = [Window(at(14), at(16))]

    assert not schedule_matches(matches, courts, windows).fits
    shortfall = determine_shortfall(matches, courts, windows)
    assert shortfall.extra_courts == {None: 1}
    assert shortfall.extra_minutes == 60


def test_dependency_of_a_match_that_does_not_fit() -> None:
    first = MatchToPlan(MatchId(1), 90, 0, frozenset({"A", "B"}))
    second = MatchToPlan(
        MatchId(2), 10, 0, frozenset({"C", "D"}), dependencies=(Dependency(MatchId(1), 0),)
    )
    result = schedule_matches([second, first], [CourtToPlan(CourtId(1))], [Window(at(9), at(10))])
    assert result.unscheduled == [MatchId(1), MatchId(2)]


def test_window_start_for_moves_matches_past_lunch() -> None:
    windows = [Window(at(10), at(12)), Window(at(13), at(15))]
    assert window_start_for(windows, at(9), 30) == at(10)
    assert window_start_for(windows, at(11, 30), 30) == at(11, 30)
    # Doesn't fit before 12:00 anymore, so after lunch
    assert window_start_for(windows, at(11, 45), 30) == at(13)
    # After the last window, matches follow each other
    assert window_start_for(windows, at(15), 30) == at(15)
    assert window_start_for([], at(8), 30) == at(8)
