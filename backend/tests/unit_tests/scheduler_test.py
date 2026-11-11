import random
from dataclasses import replace
from datetime import timedelta
from zoneinfo import ZoneInfo

from heliclockter import datetime_utc

from bracket.logic.planning.scheduler import (
    Assignment,
    CourtBookings,
    CourtToPlan,
    Dependency,
    IssueKind,
    MatchToPlan,
    PlanIssue,
    Window,
    determine_shortfall,
    find_plan_issues,
    merge_overlapping,
    schedule_matches,
    to_micros,
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

    result = schedule_matches(matches, courts, windows)
    assert not result.fits
    shortfall = determine_shortfall(matches, courts, windows, result)
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


def test_plan_issues_of_a_hand_made_plan() -> None:
    match1 = MatchToPlan(MatchId(1), 10, 2, frozenset({"A", "B"}), rest_minutes=10)
    match2 = MatchToPlan(MatchId(2), 10, 2, frozenset({"A", "C"}), rest_minutes=10)
    final = MatchToPlan(
        MatchId(3),
        10,
        2,
        frozenset({"W"}),
        game_format=GameFormat("7v7"),
        dependencies=(Dependency(MatchId(1), 0),),
    )
    courts = [CourtToPlan(CourtId(1)), CourtToPlan(CourtId(2), GameFormat("5v5"))]
    assignments = {
        MatchId(1): Assignment(MatchId(1), CourtId(1), at(9)),
        # Team A ends at 9:12 and needs 10 minutes rest, so 9:15 is too early
        MatchId(2): Assignment(MatchId(2), CourtId(1), at(9, 15)),
        # Before match 1 has ended, on a 5v5 court, and after the time window
        MatchId(3): Assignment(MatchId(3), CourtId(2), at(9, 55)),
    }
    issues = find_plan_issues([match1, match2, final], courts, [Window(at(9), at(10))], assignments)
    assert set(issues) == {
        PlanIssue(MatchId(2), IssueKind.TOO_LITTLE_REST, MatchId(1)),
        PlanIssue(MatchId(3), IssueKind.WRONG_GAME_FORMAT),
        PlanIssue(MatchId(3), IssueKind.OUTSIDE_TIME_WINDOWS),
    }

    # Overlaps on a court and for a team
    assignments[MatchId(2)] = Assignment(MatchId(2), CourtId(1), at(9, 5))
    assignments[MatchId(3)] = Assignment(MatchId(3), CourtId(1), at(9, 5))
    issues = find_plan_issues(
        [match1, match2, final], [CourtToPlan(CourtId(1))], [Window(at(9), at(10))], assignments
    )
    assert PlanIssue(MatchId(2), IssueKind.TEAM_OVERLAP, MatchId(1)) in issues
    assert PlanIssue(MatchId(3), IssueKind.BEFORE_DEPENDENCY, MatchId(1)) in issues
    assert PlanIssue(MatchId(3), IssueKind.COURT_OVERLAP, MatchId(1)) in issues


def test_scheduler_output_has_no_issues() -> None:
    """
    Property test: whatever the scheduler plans passes the independent checker.
    """
    rng = random.Random(7)
    for _ in range(40):
        group_count = rng.randint(1, 4)
        matches: list[MatchToPlan] = []
        for group_index in range(group_count):
            matches += [
                replace(
                    match,
                    rest_minutes=rng.choice([0, 5, 15]),
                    game_format=rng.choice([None, GameFormat("5v5"), GameFormat("7v7")]),
                )
                for match in group_matches(
                    "ABCD"[group_index],
                    rng.randint(3, 5),
                    1000 * (group_index + 1),
                    duration=rng.choice([8, 10, 15]),
                    margin=rng.choice([0, 2, 3]),
                )
            ]
        group_ids = [m.id for m in matches]
        matches.append(knockout_match(9001, group_ids, 5, priority=(1, 0, 0)))
        matches.append(knockout_match(9002, [MatchId(9001)], 10, priority=(1, 1, 0)))
        courts = [
            CourtToPlan(CourtId(i), rng.choice([None, GameFormat("5v5"), GameFormat("7v7")]))
            for i in range(rng.randint(1, 3))
        ] + [CourtToPlan(CourtId(99))]
        windows = [Window(at(9), at(12)), Window(at(13), at(18))]

        result = schedule_matches(matches, courts, windows)
        assert not find_plan_issues(matches, courts, windows, result.assignments)


def test_court_bookings_merge() -> None:
    bookings = CourtBookings()
    bookings.add(at(10), at(11))
    bookings.add(at(9), at(9, 30))
    bookings.add(at(10, 30), at(12))  # Overlaps the first: merged
    bookings.add(at(12), at(12, 10))  # Touches: merged
    assert bookings.starts == [to_micros(at(9)), to_micros(at(10))]
    assert bookings.ends == [to_micros(at(9, 30)), to_micros(at(12, 10))]

    match = MatchToPlan(MatchId(1), duration_minutes=20, margin_minutes=5, teams=frozenset())
    windows = [(to_micros(at(9)), to_micros(at(18)))]
    # 9:30-9:55 fits before 10:00; 9:40 would overlap with its margin
    assert bookings.earliest_start(to_micros(at(9)), match, windows, None) == to_micros(at(9, 30))
    assert bookings.earliest_start(to_micros(at(9, 40)), match, windows, None) == to_micros(
        at(12, 10)
    )
    # Not before the best start of another court
    assert bookings.earliest_start(to_micros(at(9, 40)), match, windows, to_micros(at(12))) is None


def test_merge_overlapping_windows() -> None:
    windows = [Window(at(13), at(15)), Window(at(9), at(12)), Window(at(11), at(12, 30))]
    assert merge_overlapping(windows + [Window(at(15), at(16))]) == [
        Window(at(9), at(12, 30)),
        Window(at(13), at(15)),
        Window(at(15), at(16)),  # Touching windows stay separate: no match across them
    ]
