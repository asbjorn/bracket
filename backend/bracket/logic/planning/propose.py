"""
Proposing and applying a complete match plan for a tournament, see `scheduler.py`.
"""

from collections import defaultdict
from dataclasses import replace
from datetime import timedelta

from heliclockter import datetime_utc
from pydantic import BaseModel, Field

from bracket.database import database
from bracket.logic.planning.conflicts import handle_conflicts
from bracket.logic.planning.scheduler import (
    Assignment,
    CourtToPlan,
    Dependency,
    IssueKind,
    MatchToPlan,
    ScheduleResult,
    Window,
    determine_shortfall,
    find_plan_issues,
    schedule_matches,
)
from bracket.logic.planning.timing import (
    get_category_per_match,
    get_effective_minutes,
    get_min_rest_minutes,
)
from bracket.models.db.category import Category
from bracket.models.db.game_format import GameFormat
from bracket.models.db.match import MatchWithDetails, MatchWithDetailsDefinitive
from bracket.models.db.time_window import TimeWindow
from bracket.models.db.tournament import Tournament
from bracket.models.db.util import StageWithStageItems
from bracket.sql.categories import get_all_categories_in_tournament
from bracket.sql.courts import get_all_courts_in_tournament
from bracket.sql.matches import sql_apply_default_timing, sql_set_match_slot
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.time_windows import get_own_time_windows, get_time_windows
from bracket.sql.tournaments import sql_get_tournament
from bracket.utils.id_types import CategoryId, CourtId, MatchId, TournamentId

# Without time windows, matches are planned from the start time of the tournament onward
DEFAULT_WINDOW_HOURS = 12

AnyMatch = MatchWithDetailsDefinitive | MatchWithDetails


class ProposedMatch(BaseModel):
    match_id: MatchId
    court_id: CourtId
    start_time: datetime_utc


class ExtraCourts(BaseModel):
    # `None`: courts without a specific game format
    game_format: GameFormat | None
    count: int


class ScheduleProposal(BaseModel):
    matches_total: int
    unscheduled_match_ids: list[MatchId]
    first_start: datetime_utc | None
    last_end: datetime_utc | None
    # Court time needed by all matches (incl. margins) vs. court time in the time windows
    required_court_minutes: int
    available_court_minutes: int
    uses_default_window: bool
    # What's missing when not all matches fit; `None` means not even the maximum we tried
    extra_courts: list[ExtraCourts] | None
    extra_minutes: int | None
    matches: list[ProposedMatch]


def is_fixed(match: AnyMatch) -> bool:
    """Played and started matches (also a live score) stay where they are."""
    has_score = match.stage_item_input1_score > 0 or match.stage_item_input2_score > 0
    in_progress = match.played or match.started_at is not None or has_score
    return in_progress and match.start_time is not None and match.court_id is not None


def get_stage_index_per_class(stages: list[StageWithStageItems]) -> dict[int, int]:
    """Stages are played in order of creation, separately per age class."""
    stages_per_class: dict[int | None, list[StageWithStageItems]] = defaultdict(list)
    for stage in sorted(stages, key=lambda stage: stage.id):
        stages_per_class[stage.category_id].append(stage)
    return {
        stage.id: index
        for class_stages in stages_per_class.values()
        for index, stage in enumerate(class_stages)
    }


def get_matches_to_plan(
    tournament: Tournament,
    stages: list[StageWithStageItems],
    categories: list[Category],
    category_windows: dict[CategoryId, list[TimeWindow]] | None = None,
) -> list[MatchToPlan]:
    """`category_windows`: the days/hours of the classes that have their own."""
    windows_per_class = {
        category_id: tuple(Window(w.start_time, w.end_time) for w in windows)
        for category_id, windows in (category_windows or {}).items()
        if len(windows) > 0
    }
    category_per_match = get_category_per_match(stages, categories)
    stage_index = get_stage_index_per_class(stages)
    class_order = {category.id: index for index, category in enumerate(categories, start=1)}

    matches_per_stage: dict[int, list[AnyMatch]] = {
        stage.id: [m for item in stage.stage_items for r in item.rounds for m in r.matches]
        for stage in stages
    }
    previous_stage: dict[int, int] = {}
    for class_id in {stage.category_id for stage in stages}:
        class_stages = sorted(
            (stage for stage in stages if stage.category_id == class_id), key=lambda s: s.id
        )
        for earlier, later in zip(class_stages, class_stages[1:], strict=False):
            previous_stage[later.id] = earlier.id

    result: list[MatchToPlan] = []
    for stage in stages:
        stage_buffer = tournament.stage_buffer_minutes
        for item_index, stage_item in enumerate(sorted(stage.stage_items, key=lambda i: i.name)):
            for round_index, round_ in enumerate(sorted(stage_item.rounds, key=lambda r: r.id)):
                for match in round_.matches:
                    category = category_per_match.get(match.id)
                    rest = get_min_rest_minutes(category, tournament)
                    dependencies = [
                        Dependency(feeder, rest)
                        for feeder in (
                            match.stage_item_input1_winner_from_match_id,
                            match.stage_item_input2_winner_from_match_id,
                            match.stage_item_input1_loser_from_match_id,
                            match.stage_item_input2_loser_from_match_id,
                        )
                        if feeder is not None
                    ]
                    if stage.id in previous_stage:
                        dependencies += [
                            Dependency(earlier.id, max(stage_buffer, rest))
                            for earlier in matches_per_stage[previous_stage[stage.id]]
                        ]
                    fixed = is_fixed(match)
                    result.append(
                        MatchToPlan(
                            id=match.id,
                            duration_minutes=get_effective_minutes(
                                match.custom_duration_minutes,
                                category.duration_minutes if category else None,
                                tournament.duration_minutes,
                            ),
                            margin_minutes=get_effective_minutes(
                                match.custom_margin_minutes,
                                category.margin_minutes if category else None,
                                tournament.margin_minutes,
                            ),
                            teams=frozenset(
                                f"input:{input_id}"
                                for input_id in (
                                    match.stage_item_input1_id,
                                    match.stage_item_input2_id,
                                )
                                if input_id is not None
                            ),
                            rest_minutes=rest,
                            game_format=category.game_format if category else None,
                            dependencies=tuple(dependencies),
                            priority=(
                                stage_index[stage.id],
                                round_index,
                                class_order.get(stage.category_id, 0)
                                if stage.category_id is not None
                                else 0,
                                item_index,
                            ),
                            fixed_court_id=match.court_id if fixed else None,
                            fixed_start=match.start_time if fixed else None,
                            windows=windows_per_class.get(category.id) if category else None,
                            max_per_day=category.get_max_matches_per_day() if category else None,
                        )
                    )
    return result


async def get_planning_input(
    tournament_id: TournamentId,
) -> tuple[list[MatchToPlan], list[CourtToPlan], list[Window], bool]:
    """Read only: proposing and checking a plan change nothing."""
    tournament = await sql_get_tournament(tournament_id)
    stages = await get_full_tournament_details(tournament_id)
    categories = await get_all_categories_in_tournament(tournament_id)
    court_windows, category_windows = await get_own_time_windows(tournament_id)
    courts = [
        CourtToPlan(
            court.id,
            court.game_format,
            parent_id=court.parent_court_id,
            windows=(
                tuple(Window(w.start_time, w.end_time) for w in court_windows[court.id])
                if court_windows.get(court.id)
                else None
            ),
        )
        for court in await get_all_courts_in_tournament(tournament_id)
    ]
    windows = [Window(w.start_time, w.end_time) for w in await get_time_windows(tournament_id)]
    uses_default_window = len(windows) < 1
    if uses_default_window:
        windows = [
            Window(
                tournament.start_time,
                tournament.start_time + timedelta(hours=DEFAULT_WINDOW_HOURS),
            )
        ]
    matches = get_matches_to_plan(tournament, stages, categories, category_windows)
    return matches, courts, windows, uses_default_window


def to_proposal(
    matches: list[MatchToPlan],
    courts: list[CourtToPlan],
    windows: list[Window],
    result: ScheduleResult,
    *,
    uses_default_window: bool,
) -> ScheduleProposal:
    match_by_id = {match.id: match for match in matches}
    window_minutes = sum((w.end - w.start).total_seconds() // 60 for w in windows)
    ends = [a.end(match_by_id[a.match_id]) for a in result.assignments.values()]
    shortfall = determine_shortfall(matches, courts, windows, result)
    return ScheduleProposal(
        matches_total=len(matches),
        unscheduled_match_ids=result.unscheduled,
        first_start=min((a.start for a in result.assignments.values()), default=None),
        last_end=max(ends, default=None),
        required_court_minutes=sum(m.duration_minutes + m.margin_minutes for m in matches),
        available_court_minutes=int(window_minutes * len(courts)),
        uses_default_window=uses_default_window,
        extra_courts=(
            None
            if shortfall.extra_courts is None
            else [
                ExtraCourts(game_format=game_format, count=count)
                for game_format, count in shortfall.extra_courts.items()
            ]
        ),
        extra_minutes=shortfall.extra_minutes,
        matches=[
            ProposedMatch(match_id=a.match_id, court_id=a.court_id, start_time=a.start)
            for a in sorted(result.assignments.values(), key=lambda a: (a.start, a.court_id))
        ],
    )


async def propose_schedule(tournament_id: TournamentId) -> ScheduleProposal:
    matches, courts, windows, uses_default_window = await get_planning_input(tournament_id)
    result = schedule_matches(matches, courts, windows)
    return to_proposal(matches, courts, windows, result, uses_default_window=uses_default_window)


async def apply_schedule(tournament_id: TournamentId) -> ScheduleProposal:
    """
    Plans all matches and saves the result. Matches that don't fit are left unplanned.
    """
    matches, courts, windows, uses_default_window = await get_planning_input(tournament_id)
    result = schedule_matches(matches, courts, windows)

    # Save the match lengths the plan was made with
    await sql_apply_default_timing(tournament_id)
    per_court: dict[CourtId, list[MatchId]] = defaultdict(list)
    for assignment in sorted(result.assignments.values(), key=lambda a: a.start):
        per_court[assignment.court_id].append(assignment.match_id)

    for court_id, match_ids in per_court.items():
        for position, match_id in enumerate(match_ids):
            await sql_set_match_slot(
                match_id, court_id, result.assignments[match_id].start, position
            )
    for match_id in result.unscheduled:
        await sql_set_match_slot(match_id, None, None, None)

    await handle_conflicts(await get_full_tournament_details(tournament_id))
    return to_proposal(matches, courts, windows, result, uses_default_window=uses_default_window)


class PlanIssueOut(BaseModel):
    match_id: MatchId
    kind: IssueKind
    other_match_id: MatchId | None


async def get_current_plan_issues(tournament_id: TournamentId) -> list[PlanIssueOut]:
    """
    Checks the current plan (also after manual changes): overlaps, rest, time windows,
    game formats and the order of knockout rounds.
    """
    matches, courts, windows, _ = await get_planning_input(tournament_id)
    stages = await get_full_tournament_details(tournament_id)
    assignments = {
        match.id: Assignment(match.id, match.court_id, match.start_time)
        for stage in stages
        for stage_item in stage.stage_items
        for round_ in stage_item.rounds
        for match in round_.matches
        if match.court_id is not None and match.start_time is not None
    }
    return [
        PlanIssueOut(match_id=i.match_id, kind=i.kind, other_match_id=i.other_match_id)
        for i in find_plan_issues(matches, courts, windows, assignments)
    ]


class ReplanBody(BaseModel):
    """
    Changing the schedule during the cup. Played and started matches stay where they are.

    - Without `keep_courts` ("a new schedule from now"): all other matches are planned again,
      not before `from_time`.
    - With `keep_courts` (a delay): matches keep their pitch and order. The selected matches (all,
      one court or one class) start no earlier than `from_time + delay_minutes`; the others
      keep their time unless a delayed match pushes them (same pitch, rest, knockout order).
      Gaps such as the lunch break absorb the delay.
    """

    from_time: datetime_utc
    delay_minutes: int = Field(default=0, ge=0, le=600)
    court_id: CourtId | None = None
    category_id: CategoryId | None = None
    keep_courts: bool = False


class MatchChange(BaseModel):
    match_id: MatchId
    old_start: datetime_utc | None
    new_start: datetime_utc | None
    old_court_id: CourtId | None
    new_court_id: CourtId | None


class ReplanPreview(BaseModel):
    proposal: ScheduleProposal
    moved: int
    unchanged: int
    # The largest change of a start time, in minutes (later or earlier)
    max_shift_minutes: int
    # Teams (or group places) with at least one match that moves
    teams_affected: int
    changes: list[MatchChange]


Current = dict[MatchId, tuple[CourtId | None, datetime_utc | None]]


def plan_from(
    matches: list[MatchToPlan], current: Current, body: ReplanBody, selected: set[MatchId]
) -> list[MatchToPlan]:
    """The matches to plan again, with the rules of `ReplanBody`."""
    from_time = body.from_time
    delayed_from = from_time + timedelta(minutes=body.delay_minutes)
    result: list[MatchToPlan] = []
    for match in matches:
        if match.fixed_start is not None:
            result.append(match)
            continue
        court_id, start = current.get(match.id, (None, None))
        if not body.keep_courts:
            result.append(replace(match, earliest=from_time))
            continue
        if start is None or court_id is None:
            # Not planned yet: after everything that is
            result.append(replace(match, earliest=from_time, priority=(1, *match.priority)))
            continue
        earliest = max(start, delayed_from if match.id in selected else from_time)
        result.append(
            replace(
                match,
                earliest=earliest,
                only_court_id=court_id,
                # Keep the order: by the current start time
                priority=(0, int(start.timestamp()), *match.priority),
            )
        )
    return result


async def get_current_slots(
    tournament_id: TournamentId,
) -> tuple[Current, dict[MatchId, int | None]]:
    """The current pitch and time of every match, and the class of every match."""
    stages = await get_full_tournament_details(tournament_id)
    current: Current = {}
    class_of: dict[MatchId, int | None] = {}
    for stage in stages:
        for stage_item in stage.stage_items:
            for round_ in stage_item.rounds:
                for match in round_.matches:
                    current[match.id] = (match.court_id, match.start_time)
                    class_of[match.id] = stage.category_id
    return current, class_of


async def make_replan(tournament_id: TournamentId, body: ReplanBody) -> ReplanPreview:
    matches, courts, windows, uses_default_window = await get_planning_input(tournament_id)
    current, class_of = await get_current_slots(tournament_id)
    selected = {
        match_id
        for match_id, (court_id, _) in current.items()
        if (body.court_id is None or court_id == body.court_id)
        and (body.category_id is None or class_of.get(match_id) == body.category_id)
    }
    to_plan = plan_from(matches, current, body, selected)
    result = schedule_matches(to_plan, courts, windows)
    proposal = to_proposal(
        to_plan, courts, windows, result, uses_default_window=uses_default_window
    )

    changes: list[MatchChange] = []
    shifts: list[int] = []
    teams: set[str] = set()
    for match in to_plan:
        old_court, old_start = current.get(match.id, (None, None))
        assignment = result.assignments.get(match.id)
        new_court = assignment.court_id if assignment else None
        new_start = assignment.start if assignment else None
        if (old_court, old_start) == (new_court, new_start):
            continue
        changes.append(
            MatchChange(
                match_id=match.id,
                old_start=old_start,
                new_start=new_start,
                old_court_id=old_court,
                new_court_id=new_court,
            )
        )
        teams |= match.teams
        if old_start is not None and new_start is not None:
            shifts.append(abs(int((new_start - old_start).total_seconds() // 60)))
    preview = ReplanPreview(
        proposal=proposal,
        moved=len(changes),
        unchanged=len(to_plan) - len(changes),
        max_shift_minutes=max(shifts, default=0),
        teams_affected=len(teams),
        changes=sorted(changes, key=lambda c: (c.new_start is None, c.new_start or c.old_start)),
    )
    return preview


async def preview_replan(tournament_id: TournamentId, body: ReplanBody) -> ReplanPreview:
    return await make_replan(tournament_id, body)


async def apply_replan(tournament_id: TournamentId, body: ReplanBody) -> ReplanPreview:
    """Saves only the matches that change; matches that no longer fit lose their slot."""
    preview = await make_replan(tournament_id, body)
    await sql_apply_default_timing(tournament_id)
    async with database.transaction():
        for change in preview.changes:
            if change.new_court_id is None or change.new_start is None:
                await sql_set_match_slot(change.match_id, None, None, None)
            else:
                await sql_set_match_slot(
                    change.match_id, change.new_court_id, change.new_start, None
                )
    await renumber_positions(tournament_id)
    await handle_conflicts(await get_full_tournament_details(tournament_id))
    return preview


async def renumber_positions(tournament_id: TournamentId) -> None:
    """The order of the matches on each pitch, by start time."""
    await database.execute(
        """
        UPDATE matches SET position_in_schedule = numbered.position
        FROM (
            SELECT m.id, row_number() OVER (
                PARTITION BY m.court_id ORDER BY m.start_time, m.id
            ) - 1 AS position
            FROM matches m
            JOIN rounds r ON r.id = m.round_id
            JOIN stage_items si ON si.id = r.stage_item_id
            JOIN stages st ON st.id = si.stage_id
            WHERE st.tournament_id = :tournament_id AND m.court_id IS NOT NULL
        ) AS numbered
        WHERE matches.id = numbered.id
        """,
        values={"tournament_id": tournament_id},
    )
