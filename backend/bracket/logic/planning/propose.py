"""
Proposing and applying a complete match plan for a tournament, see `scheduler.py`.
"""

from collections import defaultdict
from datetime import timedelta

from heliclockter import datetime_utc
from pydantic import BaseModel

from bracket.logic.planning.conflicts import handle_conflicts
from bracket.logic.planning.scheduler import (
    CourtToPlan,
    Dependency,
    MatchToPlan,
    ScheduleResult,
    Window,
    determine_shortfall,
    schedule_matches,
)
from bracket.logic.planning.timing import get_category_per_match, get_min_rest_minutes
from bracket.models.db.category import Category
from bracket.models.db.game_format import GameFormat
from bracket.models.db.match import MatchWithDetails, MatchWithDetailsDefinitive
from bracket.models.db.tournament import Tournament
from bracket.models.db.util import StageWithStageItems
from bracket.sql.categories import get_all_categories_in_tournament
from bracket.sql.courts import get_all_courts_in_tournament
from bracket.sql.matches import sql_apply_default_timing, sql_set_match_slot
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.time_windows import get_time_windows
from bracket.sql.tournaments import sql_get_tournament
from bracket.utils.id_types import CourtId, MatchId, TournamentId

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
    """Played matches and matches with a live score stay where they are."""
    has_score = match.stage_item_input1_score > 0 or match.stage_item_input2_score > 0
    return (
        (match.played or has_score) and match.start_time is not None and match.court_id is not None
    )


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
    tournament: Tournament, stages: list[StageWithStageItems], categories: list[Category]
) -> list[MatchToPlan]:
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
                            duration_minutes=match.duration_minutes,
                            margin_minutes=match.margin_minutes,
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
                        )
                    )
    return result


async def get_planning_input(
    tournament_id: TournamentId,
) -> tuple[list[MatchToPlan], list[CourtToPlan], list[Window], bool]:
    await sql_apply_default_timing(tournament_id)
    tournament = await sql_get_tournament(tournament_id)
    stages = await get_full_tournament_details(tournament_id)
    categories = await get_all_categories_in_tournament(tournament_id)
    courts = [
        CourtToPlan(court.id, court.game_format)
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
    return get_matches_to_plan(tournament, stages, categories), courts, windows, uses_default_window


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
    shortfall = determine_shortfall(matches, courts, windows)
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
