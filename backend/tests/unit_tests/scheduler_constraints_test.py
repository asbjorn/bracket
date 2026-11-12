"""Split pitches, opening hours per pitch, days/hours per class, per-day limits, re-planning."""

import random
from dataclasses import replace
from datetime import timedelta

from bracket.logic.planning.propose import ReplanBody, plan_from
from bracket.logic.planning.scheduler import (
    Assignment,
    CourtToPlan,
    IssueKind,
    MatchToPlan,
    PlanIssue,
    Window,
    find_plan_issues,
    intersect_windows,
    schedule_matches,
    shared_ground,
)
from bracket.models.db.game_format import GameFormat
from bracket.utils.id_types import CourtId, MatchId
from tests.unit_tests.scheduler_test import DAY, at, group_matches

SEVEN = GameFormat("7v7")
ELEVEN = GameFormat("11v11")
FULL = CourtToPlan(CourtId(1), ELEVEN)
HALF_A = CourtToPlan(CourtId(2), SEVEN, parent_id=CourtId(1))
HALF_B = CourtToPlan(CourtId(3), SEVEN, parent_id=CourtId(1))


def match(
    match_id: int, teams: str, game_format: GameFormat | None, **kwargs: object
) -> MatchToPlan:
    return MatchToPlan(
        id=MatchId(match_id),
        duration_minutes=20,
        margin_minutes=0,
        teams=frozenset(teams.split()),
        game_format=game_format,
        priority=(match_id,),
        **kwargs,  # type: ignore[arg-type]
    )


def test_split_pitch_full_blocks_parts_and_parts_block_full() -> None:
    windows = [Window(at(9), at(12))]
    matches = [
        match(1, "a b", ELEVEN),  # Full pitch 09:00-09:20
        match(2, "c d", SEVEN),  # Halves can only start when the full pitch is free
        match(3, "e f", SEVEN),
        match(4, "g h", ELEVEN),  # The full pitch waits until both halves are free
    ]
    result = schedule_matches(matches, [FULL, HALF_A, HALF_B], windows)
    starts = {m: (a.court_id, a.start) for m, a in result.assignments.items()}
    assert starts[MatchId(1)] == (CourtId(1), at(9))
    # Both halves at the same time: parts don't block each other
    assert {starts[MatchId(2)], starts[MatchId(3)]} == {
        (CourtId(2), at(9, 20)),
        (CourtId(3), at(9, 20)),
    }
    assert starts[MatchId(4)] == (CourtId(1), at(9, 40))
    assert not find_plan_issues(matches, [FULL, HALF_A, HALF_B], windows, result.assignments)


def test_checker_flags_split_pitch_overlap() -> None:
    windows = [Window(at(9), at(12))]
    matches = [match(1, "a b", ELEVEN), match(2, "c d", SEVEN)]
    assignments = {
        MatchId(1): Assignment(MatchId(1), CourtId(1), at(9)),
        MatchId(2): Assignment(MatchId(2), CourtId(2), at(9, 10)),
    }
    issues = find_plan_issues(matches, [FULL, HALF_A, HALF_B], windows, assignments)
    assert issues == [PlanIssue(MatchId(2), IssueKind.SPLIT_PITCH_OVERLAP, MatchId(1))]


def test_pitch_opening_hours() -> None:
    """Pitch 2 is only open in the afternoon; the cup is open all day."""
    cup = [Window(at(9), at(17))]
    morning_court = CourtToPlan(CourtId(1))
    afternoon_court = CourtToPlan(CourtId(2), windows=(Window(at(13), at(17)),))
    matches = [match(i, f"t{i} u{i}", None) for i in range(1, 4)]
    # Only on pitch 2: it must wait for the afternoon
    only_two = [replace(m, only_court_id=CourtId(2)) for m in matches]
    result = schedule_matches(only_two, [morning_court, afternoon_court], cup)
    assert [result.assignments[m.id].start for m in only_two] == [at(13), at(13, 20), at(13, 40)]
    assert not find_plan_issues(only_two, [morning_court, afternoon_court], cup, result.assignments)
    wrong = {MatchId(1): Assignment(MatchId(1), CourtId(2), at(10))}
    assert find_plan_issues(matches[:1], [morning_court, afternoon_court], cup, wrong) == [
        PlanIssue(MatchId(1), IssueKind.OUTSIDE_TIME_WINDOWS)
    ]


def test_class_days_and_hours() -> None:
    """A class that plays only Sunday 10-12, in a two-day cup."""
    cup = [Window(at(9), at(17)), Window(at(24 + 9), at(24 + 17))]
    sunday = (Window(at(24 + 10), at(24 + 12)),)
    matches = [match(i, f"t{i} u{i}", None, windows=sunday) for i in range(1, 4)]
    result = schedule_matches(matches, [CourtToPlan(CourtId(1))], cup)
    assert [result.assignments[m.id].start for m in matches] == [
        at(24 + 10),
        at(24 + 10, 20),
        at(24 + 10, 40),
    ]
    assert not find_plan_issues(matches, [CourtToPlan(CourtId(1))], cup, result.assignments)
    saturday = {MatchId(1): Assignment(MatchId(1), CourtId(1), at(10))}
    assert find_plan_issues(matches[:1], [CourtToPlan(CourtId(1))], cup, saturday) == [
        PlanIssue(MatchId(1), IssueKind.OUTSIDE_CLASS_HOURS)
    ]
    # More than fits in the class hours: the rest is unscheduled, not moved to Saturday
    many = [match(i, f"t{i} u{i}", None, windows=sunday) for i in range(1, 9)]
    assert len(schedule_matches(many, [CourtToPlan(CourtId(1))], cup).unscheduled) == 2


def test_max_matches_per_day() -> None:
    """Team a plays 3 matches but at most 2 a day: the third moves to the next day."""
    cup = [Window(at(9), at(17)), Window(at(24 + 9), at(24 + 17))]
    matches = [match(1, "a b", None), match(2, "a c", None), match(3, "a d", None)]
    limited = [replace(m, max_per_day=2) for m in matches]
    result = schedule_matches(limited, [CourtToPlan(CourtId(1))], cup)
    assert [result.assignments[m.id].start for m in limited] == [at(9), at(9, 20), at(24 + 9)]
    assert not find_plan_issues(limited, [CourtToPlan(CourtId(1))], cup, result.assignments)
    same_day = {
        m.id: Assignment(m.id, CourtId(1), at(9) + timedelta(minutes=30 * i))
        for i, m in enumerate(limited)
    }
    assert find_plan_issues(limited, [CourtToPlan(CourtId(1))], cup, same_day) == [
        PlanIssue(MatchId(3), IssueKind.TOO_MANY_MATCHES_PER_DAY)
    ]


def test_days_are_norwegian_days() -> None:
    """23:30 UTC on June 13 is already June 14 in Norway (UTC+2): a new day for the limit."""
    late = [Window(at(21), at(24, 30))]  # 23:00-02:30 Norwegian summer time
    matches = [replace(m, max_per_day=1) for m in [match(1, "a b", None), match(2, "a c", None)]]
    result = schedule_matches(matches, [CourtToPlan(CourtId(1))], late)
    # The second match waits until midnight in Norway (22:00 UTC)
    assert result.assignments[MatchId(2)].start == at(22)


def test_not_before_and_only_court() -> None:
    cup = [Window(at(9), at(17))]
    courts = [CourtToPlan(CourtId(1)), CourtToPlan(CourtId(2))]
    matches = [
        match(1, "a b", None, earliest=at(11, 5)),
        match(2, "c d", None, only_court_id=CourtId(2)),
    ]
    result = schedule_matches(matches, courts, cup)
    assert result.assignments[MatchId(1)].start == at(11, 5)
    assert result.assignments[MatchId(2)].court_id == CourtId(2)


def test_intersect_windows() -> None:
    first = [Window(at(9), at(12)), Window(at(13), at(17))]
    second = [Window(at(11), at(14))]
    assert intersect_windows(first, second) == [Window(at(11), at(12)), Window(at(13), at(14))]


def test_scheduler_output_passes_checker_with_all_constraints() -> None:
    """Property test: split pitches, pitch hours, class hours and per-day limits."""
    rng = random.Random(11)
    for _ in range(60):
        cup = [Window(at(9), at(12)), Window(at(13), at(17)), Window(at(24 + 9), at(24 + 16))]
        courts = [
            CourtToPlan(CourtId(1), ELEVEN),
            CourtToPlan(CourtId(2), SEVEN, parent_id=CourtId(1)),
            CourtToPlan(CourtId(3), SEVEN, parent_id=CourtId(1)),
            CourtToPlan(
                CourtId(4),
                rng.choice([None, SEVEN]),
                windows=rng.choice([None, (Window(at(10), at(15)),)]),
            ),
        ]
        matches: list[MatchToPlan] = []
        for group_index in range(rng.randint(1, 3)):
            class_windows = rng.choice(
                [None, (Window(at(24 + 9), at(24 + 14)),), (Window(at(9), at(13)),)]
            )
            matches += [
                replace(
                    m,
                    game_format=rng.choice([SEVEN, ELEVEN]),
                    rest_minutes=rng.choice([0, 10]),
                    windows=class_windows,
                    max_per_day=rng.choice([None, 1, 2]),
                )
                for m in group_matches(
                    "ABC"[group_index],
                    rng.randint(3, 5),
                    100 * (group_index + 1),
                    duration=rng.choice([10, 15, 20]),
                    margin=rng.choice([0, 5]),
                )
            ]
        result = schedule_matches(matches, courts, cup)
        assert not find_plan_issues(matches, courts, cup, result.assignments)
        assert all(a.start >= DAY for a in result.assignments.values())


def test_delay_keeps_pitch_and_order_and_uses_gaps() -> None:
    """15 minutes late at 11:00: the morning slides, the lunch break absorbs the rest."""
    cup = [Window(at(9), at(12)), Window(at(12, 45), at(17))]
    court = CourtToPlan(CourtId(1))
    matches = [match(i, f"t{i} u{i}", None) for i in range(1, 6)]
    current = {
        MatchId(1): (CourtId(1), at(11)),
        MatchId(2): (CourtId(1), at(11, 20)),
        MatchId(3): (CourtId(1), at(11, 40)),
        MatchId(4): (CourtId(1), at(12, 45)),
        MatchId(5): (CourtId(1), at(14)),
    }
    body = ReplanBody(from_time=at(11), delay_minutes=15, keep_courts=True)
    planned = plan_from(matches, current, body, selected=set(current))  # type: ignore[arg-type]
    result = schedule_matches(planned, [court], cup)
    starts = [result.assignments[m.id].start for m in matches]
    # 11:15, 11:35; the third no longer fits before 12:00, so it goes first after lunch and
    # the 12:45 match follows it; the 14:00 match isn't touched
    assert starts == [at(11, 15), at(11, 35), at(12, 45), at(13, 5), at(14)]


def test_new_schedule_from_now_never_plans_in_the_past() -> None:
    cup = [Window(at(9), at(17))]
    matches = [match(i, f"t{i} u{i}", None) for i in range(1, 4)]
    current = {m.id: (CourtId(1), at(9) + timedelta(minutes=20 * i)) for i, m in enumerate(matches)}
    played = replace(matches[0], fixed_court_id=CourtId(1), fixed_start=at(9))
    body = ReplanBody(from_time=at(13))
    planned = plan_from([played, *matches[1:]], current, body, selected=set())  # type: ignore[arg-type]
    result = schedule_matches(planned, [CourtToPlan(CourtId(1))], cup)
    assert result.assignments[MatchId(1)].start == at(9)
    assert [result.assignments[m.id].start for m in matches[1:]] == [at(13), at(13, 20)]


def test_match_can_go_before_a_fixed_match_of_its_team() -> None:
    """Team a's 09:30 match is already played; its other match still fits at 09:00."""
    cup = [Window(at(9), at(17))]
    played = match(1, "a b", None, fixed_court_id=CourtId(1), fixed_start=at(9, 30))
    other = match(2, "a c", None)
    result = schedule_matches(
        [played, other], [CourtToPlan(CourtId(1)), CourtToPlan(CourtId(2))], cup
    )
    assert result.assignments[MatchId(2)].start == at(9)
    # With rest it no longer fits before (20 min + 15 rest > 30): after the played match
    rested = replace(other, rest_minutes=15)
    result = schedule_matches(
        [played, rested], [CourtToPlan(CourtId(1)), CourtToPlan(CourtId(2))], cup
    )
    assert result.assignments[MatchId(2)].start == at(9, 50)


def test_replanning_around_fixed_matches_passes_checker() -> None:
    """Property test: plan, fix a random part (played/started), plan the rest again."""
    rng = random.Random(5)
    for _ in range(60):
        cup = [Window(at(9), at(12)), Window(at(13), at(17))]
        courts = [CourtToPlan(CourtId(i), rng.choice([None, SEVEN])) for i in range(1, 4)]
        matches: list[MatchToPlan] = []
        for group_index in range(rng.randint(1, 3)):
            matches += [
                replace(m, game_format=SEVEN, rest_minutes=rng.choice([0, 10, 20]))
                for m in group_matches(
                    "ABC"[group_index], rng.randint(3, 5), 100 * (group_index + 1), duration=15
                )
            ]
        first = schedule_matches(matches, courts, cup)
        fixed_ids = {m.id for m in matches if m.id in first.assignments and rng.random() < 0.4}
        replanned = [
            replace(
                m,
                fixed_court_id=first.assignments[m.id].court_id,
                fixed_start=first.assignments[m.id].start,
            )
            if m.id in fixed_ids
            else replace(m, priority=(rng.randint(0, 9), *m.priority))
            for m in matches
        ]
        result = schedule_matches(replanned, courts, cup)
        assert not find_plan_issues(replanned, courts, cup, result.assignments)
        assert all(result.assignments[i] == first.assignments[i] for i in fixed_ids)


FIVE = GameFormat("5v5")


def test_nested_split_blocks_ancestors_and_descendants_only() -> None:
    """11er › 7er A/B › 5er A1/A2: a 5er match blocks 7er A and the 11er, not 7er B or 5er A2."""
    full = CourtToPlan(CourtId(1), ELEVEN)
    seven_a = CourtToPlan(CourtId(2), SEVEN, parent_id=CourtId(1))
    seven_b = CourtToPlan(CourtId(3), SEVEN, parent_id=CourtId(1))
    five_a1 = CourtToPlan(CourtId(4), FIVE, parent_id=CourtId(2))
    five_a2 = CourtToPlan(CourtId(5), FIVE, parent_id=CourtId(2))
    courts = [full, seven_a, seven_b, five_a1, five_a2]
    ground = shared_ground(courts)
    assert ground[CourtId(4)] == {CourtId(2), CourtId(1)}
    assert ground[CourtId(1)] == {CourtId(2), CourtId(3), CourtId(4), CourtId(5)}
    assert ground[CourtId(3)] == {CourtId(1)}

    windows = [Window(at(9), at(12))]
    matches = [
        match(1, "a b", FIVE, only_court_id=CourtId(4)),  # 5er A1 09:00
        match(2, "c d", FIVE, only_court_id=CourtId(5)),  # 5er A2 at the same time (cousin)
        match(3, "e f", SEVEN, only_court_id=CourtId(3)),  # 7er B at the same time (other half)
        match(4, "g h", SEVEN, only_court_id=CourtId(2)),  # 7er A waits for its 5er parts
        match(5, "i j", ELEVEN),  # The full pitch waits for everything
    ]
    result = schedule_matches(matches, courts, windows)
    starts = {m: a.start for m, a in result.assignments.items()}
    assert starts[MatchId(1)] == starts[MatchId(2)] == starts[MatchId(3)] == at(9)
    assert starts[MatchId(4)] == at(9, 20)
    assert starts[MatchId(5)] == at(9, 40)
    assert not find_plan_issues(matches, courts, windows, result.assignments)

    # The checker sees a grandchild/grandparent overlap
    clash = {
        MatchId(1): Assignment(MatchId(1), CourtId(4), at(9)),
        MatchId(5): Assignment(MatchId(5), CourtId(1), at(9, 10)),
    }
    issues = find_plan_issues([matches[0], matches[4]], courts, windows, clash)
    assert issues == [PlanIssue(MatchId(5), IssueKind.SPLIT_PITCH_OVERLAP, MatchId(1))]


def random_court_tree(rng: random.Random) -> list[CourtToPlan]:
    """A few full pitches, each split up to three levels deep in random ways."""
    courts: list[CourtToPlan] = []
    formats = [ELEVEN, SEVEN, FIVE, None]

    def add(parent: CourtId | None, depth: int) -> None:
        court_id = CourtId(len(courts) + 1)
        courts.append(CourtToPlan(court_id, formats[min(depth, 3)], parent_id=parent))
        if depth < 3 and rng.random() < 0.6:
            for _ in range(rng.randint(2, 3)):
                add(court_id, depth + 1)

    for _ in range(rng.randint(1, 3)):
        add(None, 0)
    return courts


def test_scheduler_output_passes_checker_on_random_pitch_trees() -> None:
    rng = random.Random(23)
    for _ in range(80):
        courts = random_court_tree(rng)
        windows = [Window(at(9), at(13)), Window(at(14), at(18))]
        matches = [
            replace(
                m,
                game_format=rng.choice([ELEVEN, SEVEN, FIVE]),
                rest_minutes=rng.choice([0, 10]),
            )
            for group_index in range(rng.randint(1, 3))
            for m in group_matches(
                "ABC"[group_index],
                rng.randint(3, 5),
                100 * (group_index + 1),
                duration=rng.choice([10, 15, 20]),
                margin=rng.choice([0, 5]),
            )
        ]
        result = schedule_matches(matches, courts, windows)
        assert not find_plan_issues(matches, courts, windows, result.assignments)
