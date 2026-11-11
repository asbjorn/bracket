"""
Automatic scheduling of matches on courts within the time windows of a tournament.

This module is pure (no database access), so it can be tested with plain data. The scheduler is
a greedy list scheduler: matches are placed one by one, in priority order, at the earliest time
that satisfies all constraints:

- the match fits inside a time window (matches don't continue past the end of a window),
- the court is free (matches on a court don't overlap, including the margin after a match),
- the court has the right game format (courts without a format fit any class),
- every team has had its rest since its previous match (and its margin),
- the matches it depends on are finished (e.g. both semifinals before the final), plus a delay.

Teams are identified by their slot in a group (stage item input), so constraints also hold for
slots whose team is not known yet. Matches whose teams are not known (later knockout rounds)
depend on the matches they get their teams from.
"""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import timedelta

from heliclockter import datetime_utc

from bracket.models.db.game_format import GameFormat
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
    return court.game_format is None or court.game_format == match.game_format


def find_start_on_court(
    ready: datetime_utc,
    match: MatchToPlan,
    booked: list[tuple[datetime_utc, datetime_utc]],
    windows: list[Window],
) -> datetime_utc | None:
    """
    The earliest start at or after `ready` where the match fits in a window and doesn't overlap
    booked intervals of the court. Candidates are `ready`, window starts and ends of bookings.
    """
    playing_time = match.duration_minutes * MINUTE
    occupied_time = (match.duration_minutes + match.margin_minutes) * MINUTE
    candidates = sorted(
        {ready}
        | {window.start for window in windows if window.start > ready}
        | {end for _, end in booked if end > ready}
    )
    for start in candidates:
        window = next((w for w in windows if w.start <= start < w.end), None)
        if window is None or start + playing_time > window.end:
            continue
        end = start + occupied_time
        if all(end <= booked_start or start >= booked_end for booked_start, booked_end in booked):
            return start
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


def best_assignment(
    match: MatchToPlan,
    ready: datetime_utc,
    courts: list[CourtToPlan],
    booked: dict[CourtId, list[tuple[datetime_utc, datetime_utc]]],
    windows: list[Window],
) -> Assignment | None:
    """The earliest start over all courts of the right format (first court on a tie)."""
    best: Assignment | None = None
    for court in courts:
        if not court_fits(court, match):
            continue
        start = find_start_on_court(ready, match, booked[court.id], windows)
        if start is not None and (best is None or start < best.start):
            best = Assignment(match.id, court.id, start)
    return best


def schedule_matches(
    matches: list[MatchToPlan], courts: list[CourtToPlan], windows: list[Window]
) -> ScheduleResult:
    windows = sorted(windows, key=lambda w: w.start)
    result = ScheduleResult()
    booked: dict[CourtId, list[tuple[datetime_utc, datetime_utc]]] = {c.id: [] for c in courts}
    team_ready: dict[str, datetime_utc] = {}
    match_by_id = {match.id: match for match in matches}

    def book(match: MatchToPlan, assignment: Assignment) -> None:
        result.assignments[match.id] = assignment
        end = assignment.end(match)
        booked.setdefault(assignment.court_id, []).append((assignment.start, end))
        for team in match.teams:
            team_ready[team] = max(team_ready.get(team, end), end + match.rest_minutes * MINUTE)

    # Matches that can't move are booked first
    movable = []
    for match in matches:
        if match.fixed_court_id is not None and match.fixed_start is not None:
            book(match, Assignment(match.id, match.fixed_court_id, match.fixed_start))
        else:
            movable.append(match)

    if len(windows) < 1:
        result.unscheduled = [match.id for match in movable]
        return result

    for match in in_dependency_order(movable):
        ready = ready_time(match, windows[0].start, result.assignments, match_by_id, team_ready)
        best = None if ready is None else best_assignment(match, ready, courts, booked, windows)
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
    matches: list[MatchToPlan], courts: list[CourtToPlan], windows: list[Window]
) -> Shortfall:
    """
    Simulates the schedule with more courts (of the game formats of the matches that didn't fit)
    and, separately, with a later end of the last time window, to tell the organiser exactly
    how many courts or how much time is missing. `None` means even the maximum wasn't enough.
    """
    result = schedule_matches(matches, courts, windows)
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
