from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from bracket.config import config
from bracket.logic.match_results import save_match
from bracket.logic.planning.conflicts import handle_conflicts
from bracket.logic.planning.matches import (
    handle_match_reschedule,
    schedule_all_unscheduled_matches,
)
from bracket.logic.planning.propose import (
    ReplanBody,
    apply_replan,
    apply_schedule,
    get_current_plan_issues,
    preview_replan,
    propose_schedule,
)
from bracket.logic.ranking.calculation import (
    recalculate_ranking_for_stage_item,
)
from bracket.logic.scheduling.upcoming_matches import (
    get_draft_round_in_stage_item,
    get_upcoming_matches_for_swiss,
)
from bracket.logic.walkovers import record_walkover_by_id
from bracket.models.db.match import (
    Match,
    MatchBody,
    MatchCreateBody,
    MatchCreateBodyFrontend,
    MatchFilter,
    MatchRescheduleBody,
)
from bracket.models.db.score_link import MatchStartedBody, WalkoverBody
from bracket.models.db.stage_item import StageType
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import user_authenticated_for_tournament
from bracket.routes.models import (
    PlanIssuesResponse,
    ReplanPreviewResponse,
    ScheduleProposalResponse,
    SingleMatchResponse,
    SuccessResponse,
    UpcomingMatchesResponse,
)
from bracket.routes.util import disallow_archived_tournament, match_dependency
from bracket.sql.courts import get_all_courts_in_tournament
from bracket.sql.matches import (
    sql_create_match,
    sql_delete_match,
    sql_set_match_started,
)
from bracket.sql.rounds import get_round_by_id
from bracket.sql.stage_items import get_stage_item
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.tournaments import sql_get_tournament
from bracket.sql.validation import check_foreign_keys_belong_to_tournament
from bracket.utils.id_types import MatchId, StageItemId, TournamentId

router = APIRouter(prefix=config.api_prefix)


@router.get(
    "/tournaments/{tournament_id}/stage_items/{stage_item_id}/upcoming_matches",
    response_model=UpcomingMatchesResponse,
)
async def get_matches_to_schedule(
    tournament_id: TournamentId,
    stage_item_id: StageItemId,
    elo_diff_threshold: int = 200,
    iterations: int = 2_000,
    only_recommended: bool = False,
    limit: int = 50,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> UpcomingMatchesResponse:
    match_filter = MatchFilter(
        elo_diff_threshold=elo_diff_threshold,
        only_recommended=only_recommended,
        limit=limit,
        iterations=iterations,
    )

    draft_round, stage_item = await get_draft_round_in_stage_item(tournament_id, stage_item_id)
    courts = await get_all_courts_in_tournament(tournament_id)
    if len(courts) <= len(draft_round.matches):
        return UpcomingMatchesResponse(data=[])

    return UpcomingMatchesResponse(
        data=get_upcoming_matches_for_swiss(match_filter, stage_item, draft_round)
    )


@router.delete("/tournaments/{tournament_id}/matches/{match_id}", response_model=SuccessResponse)
async def delete_match(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
    match: Match = Depends(match_dependency),
) -> SuccessResponse:
    round_ = await get_round_by_id(tournament_id, match.round_id)
    stage_item = await get_stage_item(tournament_id, round_.stage_item_id)

    if not round_.is_draft or stage_item.type != StageType.SWISS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete matches from draft rounds in Swiss stage items",
        )

    await sql_delete_match(match.id)

    stage_item = await get_stage_item(tournament_id, round_.stage_item_id)

    await recalculate_ranking_for_stage_item(tournament_id, stage_item)
    return SuccessResponse()


@router.post("/tournaments/{tournament_id}/matches", response_model=SingleMatchResponse)
async def create_match(
    tournament_id: TournamentId,
    match_body: MatchCreateBodyFrontend,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SingleMatchResponse:
    await check_foreign_keys_belong_to_tournament(match_body, tournament_id)

    round_ = await get_round_by_id(tournament_id, match_body.round_id)
    stage_item = await get_stage_item(tournament_id, round_.stage_item_id)

    if not round_.is_draft or stage_item.type != StageType.SWISS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only create matches in draft rounds of Swiss stage items",
        )

    tournament = await sql_get_tournament(tournament_id)
    body_with_durations = MatchCreateBody(
        **match_body.model_dump(),
        duration_minutes=tournament.duration_minutes,
        margin_minutes=tournament.margin_minutes,
    )

    return SingleMatchResponse(data=await sql_create_match(body_with_durations))


@router.post(
    "/tournaments/{tournament_id}/schedule/propose", response_model=ScheduleProposalResponse
)
async def propose_match_schedule(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> ScheduleProposalResponse:
    """
    Plans all matches on courts and times within the time windows, without saving. Played
    matches keep their place. Reports what's missing (courts or time) if not everything fits.
    """
    return ScheduleProposalResponse(data=await propose_schedule(tournament_id))


@router.post("/tournaments/{tournament_id}/schedule/apply", response_model=ScheduleProposalResponse)
async def apply_match_schedule(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> ScheduleProposalResponse:
    """
    Plans all matches like `schedule/propose` and saves the result. Matches that don't fit are
    left without a court and time.
    """
    return ScheduleProposalResponse(data=await apply_schedule(tournament_id))


@router.get("/tournaments/{tournament_id}/schedule/issues", response_model=PlanIssuesResponse)
async def get_schedule_issues(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> PlanIssuesResponse:
    """
    Problems in the current plan: overlapping matches, too little rest, matches outside the
    time windows or on a court of the wrong format, knockout matches before their feeders.
    """
    return PlanIssuesResponse(data=await get_current_plan_issues(tournament_id))


@router.post(
    "/tournaments/{tournament_id}/schedule/replan/preview", response_model=ReplanPreviewResponse
)
async def preview_schedule_change(
    tournament_id: TournamentId,
    body: ReplanBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> ReplanPreviewResponse:
    """
    What a new schedule from a moment, or a delay, would change, without saving. Played and
    started matches stay where they are; nothing is planned before `from_time`.
    """
    await check_foreign_keys_belong_to_tournament(body, tournament_id)
    return ReplanPreviewResponse(data=await preview_replan(tournament_id, body))


@router.post(
    "/tournaments/{tournament_id}/schedule/replan/apply", response_model=ReplanPreviewResponse
)
async def apply_schedule_change(
    tournament_id: TournamentId,
    body: ReplanBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> ReplanPreviewResponse:
    """Like the preview, and saves the matches that change."""
    await check_foreign_keys_belong_to_tournament(body, tournament_id)
    return ReplanPreviewResponse(data=await apply_replan(tournament_id, body))


@router.post("/tournaments/{tournament_id}/schedule_matches", response_model=SuccessResponse)
async def schedule_matches(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    await schedule_all_unscheduled_matches(tournament_id)
    return SuccessResponse()


@router.post(
    "/tournaments/{tournament_id}/matches/{match_id}/reschedule", response_model=SuccessResponse
)
async def reschedule_match(
    tournament_id: TournamentId,
    match_id: MatchId,
    body: MatchRescheduleBody,
    tournament: Tournament = Depends(disallow_archived_tournament),
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> SuccessResponse:
    await check_foreign_keys_belong_to_tournament(body, tournament_id)
    await handle_match_reschedule(tournament, body, match_id)
    await handle_conflicts(await get_full_tournament_details(tournament_id))
    return SuccessResponse()


@router.post(
    "/tournaments/{tournament_id}/matches/{match_id}/walkover", response_model=SuccessResponse
)
async def give_walkover(
    tournament_id: TournamentId,
    match_id: MatchId,
    body: WalkoverBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    """The other team didn't show up: `winner_team_id` wins by the tournament's walkover score."""
    await record_walkover_by_id(tournament_id, match_id, body.winner_team_id)
    return SuccessResponse()


@router.put(
    "/tournaments/{tournament_id}/matches/{match_id}/started", response_model=SuccessResponse
)
async def mark_started(
    body: MatchStartedBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
    match: Match = Depends(match_dependency),
) -> SuccessResponse:
    """Kick-off: a started match keeps its pitch and time when the schedule is changed."""
    await sql_set_match_started(match.id, body.started)
    return SuccessResponse()


@router.put("/tournaments/{tournament_id}/matches/{match_id}", response_model=SuccessResponse)
async def update_match_by_id(
    tournament_id: TournamentId,
    match_id: MatchId,
    match_body: MatchBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
    match: Match = Depends(match_dependency),
) -> SuccessResponse:
    await check_foreign_keys_belong_to_tournament(match_body, tournament_id)
    await save_match(tournament_id, match, match_body)
    return SuccessResponse()
