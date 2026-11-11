"""
Automatic scheduling of matches on courts within the time windows of a tournament.

This module is pure (no database access), so it can be tested with plain data. The scheduler is
a greedy list scheduler: matches are placed one by one, in priority order, at the earliest time
that satisfies all constraints:

- the match fits inside a time window (matches don't continue past the end of a window),
- the court is free (matches on a court don't overlap, including the margin after a match),
- the court has the right game format (courts without a format fit any class),
- every team has had its rest since its previous match (and its margin),
- the matches it depends on are finished (e.g. both semifinals before the final), plus a delay,
- a split pitch: a match on the full pitch blocks its parts, a match on a part blocks the full
  pitch (the parts don't block each other),
- a pitch with its own opening hours is only used then; a class with its own days or hours is
  only planned then,
- a team plays at most the class's number of matches a day (days in Norwegian time),
- when re-planning during the cup: not before a given time, and optionally on the same pitch.

Teams are identified by their slot in a group (stage item input), so constraints also hold for
slots whose team is not known yet. Matches whose teams are not known (later knockout rounds)
depend on the matches they get their teams from.
"""

from bisect import bisect_left, bisect_right
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from heliclockter import datetime_utc

from bracket.models.db.game_format import GameFormat
from bracket.utils.cup_time import cup_day, next_cup_midnight
from bracket.utils.id_types import CourtId, MatchId

MINUTE = timedelta(minutes=1)


@dataclass(frozen=True)
class Window:
    start: datetime_utc
    end: datetime_utc


@dataclass(frozen=True)
class CourtToPlan:
    id: CourtId
    game_format: GameFormat | None = None
    # A part of a split pitch: the full pitch it belongs to (one level only)
    parent_id: CourtId | None = None
    # Its own opening hours; `None`: the time windows of the cup
    windows: tuple[Window, ...] | None = None


@dataclass(frozen=True)
class Dependency:
    """The match can only start `delay_minutes` after the end of `match_id` (incl. margin)."""

    match_id: MatchId
    delay_minutes: int


@dataclass(frozen=True)
class MatchToPlan:  # pylint: disable=too-many-instance-attributes  # plain data
    id: MatchId
    duration_minutes: int
    margin_minutes: int
    # Teams (or slots) playing this match; they need `rest_minutes` between their matches
    teams: frozenset[str]
    rest_minutes: int = 0
    game_format: GameFormat | None = None
    dependencies: tuple[Dependency, ...] = ()
    # Lower is scheduled earlier
    priority: tuple[int, ...] = ()
    # Matches that are already played or being played keep their place
    fixed_court_id: CourtId | None = None
    fixed_start: datetime_utc | None = None
    # The days/hours of the match's class; `None`: any time the court is open
    windows: tuple[Window, ...] | None = None
    # At most this many matches a day for each of its teams (days in Norwegian time)
    max_per_day: int | None = None
    # Not before this moment (re-planning during the cup never plans in the past)
    earliest: datetime_utc | None = None
    # Only on this court (a delay keeps matches on their pitch)
    only_court_id: CourtId | None = None


@dataclass(frozen=True)
class Assignment:
    match_id: MatchId
    court_id: CourtId
    start: datetime_utc

    def end(self, match: MatchToPlan) -> datetime_utc:
        """End including the margin (changeover) after the match."""
        return self.start + (match.duration_minutes + match.margin_minutes) * MINUTE


@dataclass
class ScheduleResult:
    assignments: dict[MatchId, Assignment] = field(default_factory=dict)
    unscheduled: list[MatchId] = field(default_factory=list)

    @property
    def fits(self) -> bool:
        return len(self.unscheduled) < 1


def court_fits(court: CourtToPlan, match: MatchToPlan) -> bool:
    if match.only_court_id is not None and court.id != match.only_court_id:
        return False
    return court.game_format is None or court.game_format == match.game_format


def courts_share_ground(court1: CourtToPlan, court2: CourtToPlan) -> bool:
    """A full pitch and one of its parts can't be used at the same time (two parts can)."""
    return court1.parent_id == court2.id or court2.parent_id == court1.id


def intersect_windows(first: list[Window], second: list[Window]) -> list[Window]:
    """The times in both lists of sorted, disjoint windows."""
    result: list[Window] = []
    i = j = 0
    while i < len(first) and j < len(second):
        start = max(first[i].start, second[j].start)
        end = min(first[i].end, second[j].end)
        if start < end:
            result.append(Window(start, end))
        if first[i].end < second[j].end:
            i += 1
        else:
            j += 1
    return result


def effective_windows(
    court: CourtToPlan | None, match: MatchToPlan, cup_windows: list[Window]
) -> list[Window]:
    """When a match may be played on a court: the court's hours (or the cup's) and its class's."""
    court_windows = (
        merge_overlapping(list(court.windows))
        if court is not None and court.windows is not None
        else cup_windows
    )
    if match.windows is None:
        return court_windows
    return intersect_windows(court_windows, merge_overlapping(list(match.windows)))


EPOCH = datetime_utc(1970, 1, 1, tzinfo=ZoneInfo("UTC"))
MICROSECOND = timedelta(microseconds=1)


def to_micros(moment: datetime_utc) -> int:
    """Exact integer time for the hot loop; datetime arithmetic is much slower."""
    return (moment - EPOCH) // MICROSECOND


def from_micros(micros: int) -> datetime_utc:
    return EPOCH + micros * MICROSECOND


class CourtBookings:
    """
    The busy time of one court as sorted, disjoint intervals in microseconds (touching or
    overlapping bookings are merged), so the earliest free start is found with binary search.
    """

    def __init__(self) -> None:
        self.starts: list[int] = []
        self.ends: list[int] = []

    def add(self, start: datetime_utc, end: datetime_utc) -> None:
        start_us, end_us = to_micros(start), to_micros(end)
        first = bisect_left(self.ends, start_us)  # First interval ending at or after the start
        last = bisect_right(self.starts, end_us)  # After the last one starting at or before the end
        if first < last:
            start_us = min(start_us, self.starts[first])
            end_us = max(end_us, self.ends[last - 1])
        self.starts[first:last] = [start_us]
        self.ends[first:last] = [end_us]

    def overlap_end(self, start: int, end: int) -> int | None:
        """The end of a booking that overlaps [start, end), if there is one."""
        booking = bisect_right(self.ends, start)  # First booking that ends after the start
        if booking < len(self.starts) and self.starts[booking] < end:
            return self.ends[booking]
        return None

    def earliest_start(
        self, ready: int, match: MatchToPlan, windows: list[tuple[int, int]], before: int | None
    ) -> int | None:
        """
        The earliest start at or after `ready` (and before `before`) where the match is played
        within one window and the match plus its margin doesn't overlap a booking. `windows` are
        sorted, disjoint (start, end) pairs.
        """
        playing_time = match.duration_minutes * 60_000_000
        occupied_time = (match.duration_minutes + match.margin_minutes) * 60_000_000
        start = ready
        window_index = bisect_right(windows, start, key=lambda window: window[1])
        while window_index < len(windows) and (before is None or start < before):
            window_start, window_end = windows[window_index]
            start = max(start, window_start)
            if start + playing_time > window_end:
                window_index += 1
                continue
            booking = bisect_right(self.ends, start)  # First booking that ends after the start
            if booking < len(self.starts) and self.starts[booking] < start + occupied_time:
                start = self.ends[booking]
                continue
            return start if before is None or start < before else None
        return None


def in_dependency_order(matches: list[MatchToPlan]) -> list[MatchToPlan]:
    """
    Matches by priority, but never before the matches they depend on.
    """
    remaining = sorted(matches, key=lambda m: (m.priority, m.id))
    remaining_ids = {match.id for match in remaining}
    ordered: list[MatchToPlan] = []
    while remaining:
        index = next(
            (
                i
                for i, match in enumerate(remaining)
                if all(d.match_id not in remaining_ids for d in match.dependencies)
            ),
            0,  # A dependency cycle can't happen in a tournament; don't loop forever if it does
        )
        match = remaining.pop(index)
        remaining_ids.discard(match.id)
        ordered.append(match)
    return ordered


def ready_time(
    match: MatchToPlan,
    earliest: datetime_utc,
    assignments: dict[MatchId, Assignment],
    match_by_id: dict[MatchId, MatchToPlan],
    team_ready: dict[str, datetime_utc],
) -> datetime_utc | None:
    """
    When the match can start at the earliest: after its dependencies (plus their delay) and
    after the rest of its teams. `None` if a dependency couldn't be scheduled.
    """
    ready = earliest
    for dependency in match.dependencies:
        assignment = assignments.get(dependency.match_id)
        if assignment is None:
            if dependency.match_id in match_by_id:
                return None
            continue
        dependency_end = assignment.end(match_by_id[dependency.match_id])
        ready = max(ready, dependency_end + dependency.delay_minutes * MINUTE)
    for team in match.teams:
        ready = max(ready, team_ready.get(team, ready))
    return ready


def best_assignment(  # pylint: disable=too-many-arguments
    match: MatchToPlan,
    ready: datetime_utc,
    courts: list[CourtToPlan],
    booked: dict[CourtId, CourtBookings],
    spans_for: Callable[[CourtToPlan, MatchToPlan], list[tuple[int, int]]],
    team_conflict_end: Callable[[MatchToPlan, int], int | None] = lambda _match, _start: None,
) -> Assignment | None:
    """
    The earliest start over all courts of the right format (first court on a tie).
    `team_conflict_end`: when a start clashes with a fixed match of one of its teams, the end
    of that clash (with rest), else `None`.
    """
    ready_us = to_micros(ready)
    best: tuple[int, CourtId] | None = None
    for court in courts:
        if not court_fits(court, match):
            continue
        # Only a strictly earlier start beats the best court so far
        before = None if best is None else best[0]
        start = booked[court.id].earliest_start(ready_us, match, spans_for(court, match), before)
        while start is not None and (clash := team_conflict_end(match, start)) is not None:
            start = booked[court.id].earliest_start(clash, match, spans_for(court, match), before)
        if start is not None:
            best = (start, court.id)
            if start == ready_us:
                break  # No court can do better
    return None if best is None else Assignment(match.id, best[1], from_micros(best[0]))


def merge_overlapping(windows: list[Window]) -> list[Window]:
    """Sorted windows where overlapping ones are joined (touching ones stay separate)."""
    merged: list[Window] = []
    for window in sorted(windows, key=lambda w: w.start):
        if merged and window.start < merged[-1].end:
            merged[-1] = Window(merged[-1].start, max(merged[-1].end, window.end))
        else:
            merged.append(window)
    return merged


class DayCounts:
    """How many matches each team (slot) plays per day, for the per-day limit of a class."""

    def __init__(self) -> None:
        self.counts: dict[tuple[str, date], int] = {}

    def add(self, match: MatchToPlan, start: datetime_utc) -> None:
        day = cup_day(start)
        for team in match.teams:
            self.counts[(team, day)] = self.counts.get((team, day), 0) + 1

    def is_full(self, match: MatchToPlan, start: datetime_utc) -> bool:
        if match.max_per_day is None:
            return False
        day = cup_day(start)
        return any(self.counts.get((team, day), 0) >= match.max_per_day for team in match.teams)


def schedule_matches(
    matches: list[MatchToPlan], courts: list[CourtToPlan], windows: list[Window]
) -> ScheduleResult:
    windows = merge_overlapping(windows)
    result = ScheduleResult()
    booked = {court.id: CourtBookings() for court in courts}
    court_by_id = {court.id: court for court in courts}
    parts: dict[CourtId, list[CourtId]] = {}
    for court in courts:
        if court.parent_id is not None:
            parts.setdefault(court.parent_id, []).append(court.id)
    team_ready: dict[str, datetime_utc] = {}
    day_counts = DayCounts()
    match_by_id = {match.id: match for match in matches}

    def book(match: MatchToPlan, assignment: Assignment) -> None:
        result.assignments[match.id] = assignment
        end = assignment.end(match)
        court = court_by_id.get(assignment.court_id)
        # The full pitch and its parts share the ground (the parts don't block each other)
        blocked = [assignment.court_id, *parts.get(assignment.court_id, [])]
        if court is not None and court.parent_id is not None:
            blocked.append(court.parent_id)
        for court_id in blocked:
            booked.setdefault(court_id, CourtBookings()).add(assignment.start, end)
        if match.fixed_start is not None:
            # A fixed match is a busy interval of its teams: others can be before or after it
            for team in match.teams:
                team_fixed.setdefault(team, CourtBookings()).add(
                    assignment.start, end + match.rest_minutes * MINUTE
                )
        else:
            for team in match.teams:
                team_ready[team] = max(team_ready.get(team, end), end + match.rest_minutes * MINUTE)
        day_counts.add(match, assignment.start)

    def team_conflict_end(match: MatchToPlan, start: int) -> int | None:
        """A clash with a fixed match of one of the teams: when it ends (with its rest)."""
        end = start + (match.duration_minutes + match.margin_minutes + match.rest_minutes) * (
            60_000_000
        )
        clashes = [
            clash
            for team in match.teams
            if team in team_fixed
            and (clash := team_fixed[team].overlap_end(start, end)) is not None
        ]
        return max(clashes, default=None)

    # Matches that can't move are booked first
    team_fixed: dict[str, CourtBookings] = {}
    movable = []
    for match in matches:
        if match.fixed_court_id is not None and match.fixed_start is not None:
            book(match, Assignment(match.id, match.fixed_court_id, match.fixed_start))
        else:
            movable.append(match)

    if len(windows) < 1 and not any(court.windows for court in courts):
        result.unscheduled = [match.id for match in movable]
        return result

    spans_cache: dict[tuple[CourtId, tuple[Window, ...] | None], list[tuple[int, int]]] = {}

    def spans_for(court: CourtToPlan, match: MatchToPlan) -> list[tuple[int, int]]:
        key = (court.id, match.windows)
        if key not in spans_cache:
            spans_cache[key] = [
                (to_micros(w.start), to_micros(w.end))
                for w in effective_windows(court, match, windows)
            ]
        return spans_cache[key]

    first_start = min(
        [w.start for w in windows] + [w.start for c in courts for w in c.windows or ()]
    )
    for match in in_dependency_order(movable):
        earliest = first_start if match.earliest is None else max(first_start, match.earliest)
        ready = ready_time(match, earliest, result.assignments, match_by_id, team_ready)
        best = None
        while ready is not None:
            best = best_assignment(match, ready, courts, booked, spans_for, team_conflict_end)
            if best is None or not day_counts.is_full(match, best.start):
                break
            # This day is full for one of its teams: try from the next day
            ready, best = next_cup_midnight(best.start), None
        if best is None:
            result.unscheduled.append(match.id)
        else:
            book(match, best)

    return result


@dataclass(frozen=True)
class Shortfall:
    """How much more is needed to fit all matches: courts per game format, or time."""

    extra_courts: dict[GameFormat | None, int] | None
    extra_minutes: int | None


MAX_EXTRA_COURTS = 32
MAX_EXTRA_MINUTES = 24 * 60
EXTRA_MINUTES_STEP = 15


def smallest_that_fits(low: int, high: int, fits: Callable[[int], bool]) -> int | None:
    """
    Binary search for the smallest value in [low, high] that fits, assuming more never hurts
    (more courts or more time). `None` if even `high` doesn't fit.
    """
    if not fits(high):
        return None
    while low < high:
        middle = (low + high) // 2
        if fits(middle):
            high = middle
        else:
            low = middle + 1
    return low


def determine_shortfall(
    matches: list[MatchToPlan],
    courts: list[CourtToPlan],
    windows: list[Window],
    result: ScheduleResult,
) -> Shortfall:
    """
    Simulates the schedule with more courts (of the game formats of the matches that didn't fit)
    and, separately, with a later end of the last time window, to tell the organiser exactly
    how many courts or how much time is missing. `None` means even the maximum wasn't enough.
    `result` is the schedule with the current courts and windows.
    """
    if result.fits:
        return Shortfall(extra_courts={}, extra_minutes=0)

    match_by_id = {match.id: match for match in matches}
    formats = sorted(
        {match_by_id[match_id].game_format for match_id in result.unscheduled},
        key=lambda game_format: "" if game_format is None else game_format.value,
    )

    def fits_with_extra_courts(count: int) -> bool:
        virtual_courts = [
            CourtToPlan(CourtId(-(index * 100 + number)), game_format)
            for index, game_format in enumerate(formats, start=1)
            for number in range(1, count + 1)
        ]
        return schedule_matches(matches, courts + virtual_courts, windows).fits

    court_count = smallest_that_fits(1, MAX_EXTRA_COURTS, fits_with_extra_courts)
    extra_courts = None if court_count is None else dict.fromkeys(formats, court_count)

    extra_minutes: int | None = None
    if len(windows) > 0:
        last = max(windows, key=lambda w: w.end)

        def fits_with_extra_steps(steps: int) -> bool:
            minutes = steps * EXTRA_MINUTES_STEP
            longer = [w for w in windows if w != last] + [
                replace(last, end=last.end + minutes * MINUTE)
            ]
            return schedule_matches(matches, courts, longer).fits

        steps = smallest_that_fits(
            1, MAX_EXTRA_MINUTES // EXTRA_MINUTES_STEP, fits_with_extra_steps
        )
        extra_minutes = None if steps is None else steps * EXTRA_MINUTES_STEP

    return Shortfall(extra_courts=extra_courts, extra_minutes=extra_minutes)


def window_start_for(
    windows: list[Window], earliest: datetime_utc, duration_minutes: int
) -> datetime_utc:
    """
    The first moment at or after `earliest` where a match of this duration fits in a window.
    After the last window (or without windows), matches simply follow each other.
    """
    for window in sorted(windows, key=lambda w: w.start):
        start = max(earliest, window.start)
        if start + duration_minutes * MINUTE <= window.end:
            return start
    return earliest


class IssueKind(StrEnum):
    TEAM_OVERLAP = "TEAM_OVERLAP"
    TOO_LITTLE_REST = "TOO_LITTLE_REST"
    COURT_OVERLAP = "COURT_OVERLAP"
    WRONG_GAME_FORMAT = "WRONG_GAME_FORMAT"
    OUTSIDE_TIME_WINDOWS = "OUTSIDE_TIME_WINDOWS"
    BEFORE_DEPENDENCY = "BEFORE_DEPENDENCY"
    # A full pitch and one of its parts used at the same time
    SPLIT_PITCH_OVERLAP = "SPLIT_PITCH_OVERLAP"
    # Outside the days/hours of the match's class
    OUTSIDE_CLASS_HOURS = "OUTSIDE_CLASS_HOURS"
    # A team plays more matches that day than its class allows
    TOO_MANY_MATCHES_PER_DAY = "TOO_MANY_MATCHES_PER_DAY"


@dataclass(frozen=True)
class PlanIssue:
    match_id: MatchId
    kind: IssueKind
    # The other match involved (overlaps, rest, dependencies)
    other_match_id: MatchId | None = None


def single_match_issues(
    match: MatchToPlan,
    assignments: dict[MatchId, Assignment],
    court_by_id: dict[CourtId, CourtToPlan],
    windows: list[Window],
    match_by_id: dict[MatchId, MatchToPlan],
) -> list[PlanIssue]:
    """Game format, opening hours, class hours and dependencies of one planned match."""
    issues: list[PlanIssue] = []
    assignment = assignments[match.id]
    court = court_by_id.get(assignment.court_id)
    if court is not None and not (
        court.game_format is None or court.game_format == match.game_format
    ):
        issues.append(PlanIssue(match.id, IssueKind.WRONG_GAME_FORMAT))
    playing_end = assignment.start + match.duration_minutes * MINUTE

    def inside(candidates: list[Window]) -> bool:
        return any(w.start <= assignment.start and playing_end <= w.end for w in candidates)

    court_windows = (
        list(court.windows) if court is not None and court.windows is not None else windows
    )
    if court_windows and not inside(merge_overlapping(court_windows)):
        issues.append(PlanIssue(match.id, IssueKind.OUTSIDE_TIME_WINDOWS))
    if match.windows is not None and not inside(merge_overlapping(list(match.windows))):
        issues.append(PlanIssue(match.id, IssueKind.OUTSIDE_CLASS_HOURS))
    for dependency in match.dependencies:
        dependency_match = match_by_id.get(dependency.match_id)
        if dependency_match is not None and dependency.match_id in assignments:
            dependency_end = assignments[dependency.match_id].end(dependency_match)
            if assignment.start < dependency_end + dependency.delay_minutes * MINUTE:
                issues.append(PlanIssue(match.id, IssueKind.BEFORE_DEPENDENCY, dependency.match_id))
    return issues


def pair_issues(
    earlier: MatchToPlan,
    later: MatchToPlan,
    assignments: dict[MatchId, Assignment],
    court_by_id: dict[CourtId, CourtToPlan],
) -> list[PlanIssue]:
    """Overlaps on a (split) pitch and of teams, and rest of teams, for two matches by start."""
    issues: list[PlanIssue] = []
    earlier_end = assignments[earlier.id].end(earlier)
    later_start = assignments[later.id].start
    earlier_court = assignments[earlier.id].court_id
    later_court = assignments[later.id].court_id
    if later_start < earlier_end:
        if earlier_court == later_court:
            issues.append(PlanIssue(later.id, IssueKind.COURT_OVERLAP, earlier.id))
        elif (
            earlier_court in court_by_id
            and later_court in court_by_id
            and courts_share_ground(court_by_id[earlier_court], court_by_id[later_court])
        ):
            issues.append(PlanIssue(later.id, IssueKind.SPLIT_PITCH_OVERLAP, earlier.id))
    if earlier.teams & later.teams:
        # Like the scheduler: a team rests after a match for the rest of that match
        if later_start < earlier_end:
            issues.append(PlanIssue(later.id, IssueKind.TEAM_OVERLAP, earlier.id))
        elif later_start < earlier_end + earlier.rest_minutes * MINUTE:
            issues.append(PlanIssue(later.id, IssueKind.TOO_LITTLE_REST, earlier.id))
    return issues


def find_plan_issues(
    matches: list[MatchToPlan],
    courts: list[CourtToPlan],
    windows: list[Window],
    assignments: dict[MatchId, Assignment],
) -> list[PlanIssue]:
    """
    Checks a plan independently of how it was made (by the scheduler or by hand). Played matches
    are checked as well, so issues stay visible until they are resolved.
    """
    match_by_id = {match.id: match for match in matches}
    court_by_id = {court.id: court for court in courts}
    planned = sorted(
        (match for match in matches if match.id in assignments),
        key=lambda m: assignments[m.id].start,
    )
    issues = [
        issue
        for match in planned
        for issue in single_match_issues(match, assignments, court_by_id, windows, match_by_id)
    ]
    for index, earlier in enumerate(planned):
        for later in planned[index + 1 :]:
            issues += pair_issues(earlier, later, assignments, court_by_id)
    day_counts = DayCounts()
    for match in planned:
        start = assignments[match.id].start
        if day_counts.is_full(match, start):
            issues.append(PlanIssue(match.id, IssueKind.TOO_MANY_MATCHES_PER_DAY))
        day_counts.add(match, start)
    return issues
