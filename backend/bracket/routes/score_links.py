import secrets

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from bracket.config import config
from bracket.logic.score_entry import (
    check_in_team,
    enter_result,
    enter_walkover,
    get_score_entry_view,
    score_link_dependency,
)
from bracket.models.db.score_link import (
    CheckInBody,
    MatchDayNoticeBody,
    ScoreEntryBody,
    ScoreLink,
    ScoreLinkBody,
    ScoreLinkCreated,
    WalkoverBody,
)
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import user_authenticated_for_tournament
from bracket.routes.models import (
    MatchDayNoticeResponse,
    MatchDayNoticesResponse,
    ScoreEntryViewResponse,
    ScoreLinkCreatedResponse,
    ScoreLinksResponse,
    SuccessResponse,
)
from bracket.routes.util import disallow_archived_tournament
from bracket.sql.score_links import (
    get_notices,
    get_score_links,
    sql_create_notice,
    sql_create_score_link,
    sql_resolve_notice,
    sql_revoke_score_link,
)
from bracket.sql.validation import check_foreign_keys_belong_to_tournament
from bracket.utils.id_types import MatchDayNoticeId, MatchId, ScoreLinkId, TeamId, TournamentId

router = APIRouter(prefix=config.api_prefix)


def not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"Could not find the {what}")


@router.get("/tournaments/{tournament_id}/score_links", response_model=ScoreLinksResponse)
async def get_tournament_score_links(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> ScoreLinksResponse:
    return ScoreLinksResponse(data=await get_score_links(tournament_id))


@router.post("/tournaments/{tournament_id}/score_links", response_model=ScoreLinkCreatedResponse)
async def create_score_link(
    tournament_id: TournamentId,
    body: ScoreLinkBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> ScoreLinkCreatedResponse:
    """
    A link for entering results without an account, for one court or the whole tournament.
    Owners and collaborators can create links: they run the match day. The token is in the
    response only this once; the frontend link is `/score/<token>`.
    """
    await check_foreign_keys_belong_to_tournament(body, tournament_id)
    token = secrets.token_urlsafe(32)
    link = await sql_create_score_link(tournament_id, body, token)
    return ScoreLinkCreatedResponse(data=ScoreLinkCreated(link=link, token=token))


@router.post(
    "/tournaments/{tournament_id}/score_links/{score_link_id}/revoke",
    response_model=SuccessResponse,
)
async def revoke_score_link(
    tournament_id: TournamentId,
    score_link_id: ScoreLinkId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> SuccessResponse:
    if not await sql_revoke_score_link(tournament_id, score_link_id):
        raise not_found("link")
    return SuccessResponse()


@router.get("/tournaments/{tournament_id}/notices", response_model=MatchDayNoticesResponse)
async def get_match_day_notices(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> MatchDayNoticesResponse:
    return MatchDayNoticesResponse(data=await get_notices(tournament_id))


@router.post(
    "/tournaments/{tournament_id}/notices/{notice_id}/resolve", response_model=SuccessResponse
)
async def resolve_match_day_notice(
    tournament_id: TournamentId,
    notice_id: MatchDayNoticeId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> SuccessResponse:
    if not await sql_resolve_notice(tournament_id, notice_id):
        raise not_found("notice")
    return SuccessResponse()


@router.get("/score/{token}", response_model=ScoreEntryViewResponse)
async def get_score_entry(
    link: ScoreLink = Depends(score_link_dependency),
) -> ScoreEntryViewResponse:
    """The matches of a score link (no account needed, the token is the key)."""
    return ScoreEntryViewResponse(data=await get_score_entry_view(link))


@router.put("/score/{token}/matches/{match_id}", response_model=SuccessResponse)
async def enter_match_result(
    match_id: MatchId, body: ScoreEntryBody, link: ScoreLink = Depends(score_link_dependency)
) -> SuccessResponse:
    await enter_result(link, match_id, body)
    return SuccessResponse()


@router.post("/score/{token}/notices", response_model=MatchDayNoticeResponse)
async def report_from_pitch(
    body: MatchDayNoticeBody, link: ScoreLink = Depends(score_link_dependency)
) -> MatchDayNoticeResponse:
    """E.g. "we're running 10 minutes late": shown to the organiser on the schedule page."""
    notice = await sql_create_notice(link.tournament_id, link.court_id, link.id, body)
    return MatchDayNoticeResponse(data=notice)


@router.put("/score/{token}/matches/{match_id}/walkover", response_model=SuccessResponse)
async def enter_match_walkover(
    match_id: MatchId, body: WalkoverBody, link: ScoreLink = Depends(score_link_dependency)
) -> SuccessResponse:
    """The other team didn't show up: `winner_team_id` wins by the tournament's walkover score."""
    await enter_walkover(link, match_id, body.winner_team_id)
    return SuccessResponse()


@router.put("/score/{token}/teams/{team_id}/check_in", response_model=SuccessResponse)
async def check_in_team_at_pitch(
    team_id: TeamId, body: CheckInBody, link: ScoreLink = Depends(score_link_dependency)
) -> SuccessResponse:
    await check_in_team(link, team_id, body.checked_in)
    return SuccessResponse()
