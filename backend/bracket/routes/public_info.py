from fastapi import APIRouter, Depends
from fastapi.responses import Response
from heliclockter import datetime_utc

from bracket.config import config
from bracket.logic.public_info import (
    get_announcement,
    get_public_notices,
    get_rules,
    set_announcement,
    set_rules,
    team_calendar,
)
from bracket.models.db.public_info import AnnouncementBody, Rules
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import (
    user_authenticated_for_tournament,
    user_authenticated_or_public_dashboard,
)
from bracket.routes.models import (
    AnnouncementResponse,
    PublicNoticesResponse,
    RulesResponse,
    SuccessResponse,
)
from bracket.routes.util import disallow_archived_tournament
from bracket.utils.id_types import TeamId, TournamentId

router = APIRouter(prefix=config.api_prefix)


@router.get("/tournaments/{tournament_id}/announcement", response_model=AnnouncementResponse)
async def get_tournament_announcement(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> AnnouncementResponse:
    """The announcement as set by the organiser, also when it has expired."""
    return AnnouncementResponse(data=await get_announcement(tournament_id))


@router.put("/tournaments/{tournament_id}/announcement", response_model=SuccessResponse)
async def update_tournament_announcement(
    tournament_id: TournamentId,
    body: AnnouncementBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    await set_announcement(tournament_id, body.announcement)
    return SuccessResponse()


@router.get("/tournaments/{tournament_id}/public_notices", response_model=PublicNoticesResponse)
async def get_tournament_public_notices(
    tournament_id: TournamentId,
    _: UserPublic | None = Depends(user_authenticated_or_public_dashboard),
) -> PublicNoticesResponse:
    """For the public pages: the current announcement and recent delays per court."""
    return PublicNoticesResponse(data=await get_public_notices(tournament_id, datetime_utc.now()))


@router.get("/tournaments/{tournament_id}/rules", response_model=RulesResponse)
async def get_tournament_rules(
    tournament_id: TournamentId,
    _: UserPublic | None = Depends(user_authenticated_or_public_dashboard),
) -> RulesResponse:
    return RulesResponse(data=await get_rules(tournament_id))


@router.put("/tournaments/{tournament_id}/rules", response_model=SuccessResponse)
async def update_tournament_rules(
    tournament_id: TournamentId,
    body: Rules,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    await set_rules(tournament_id, body)
    return SuccessResponse()


@router.get(
    "/tournaments/{tournament_id}/teams/{team_id}/calendar.ics",
    response_class=Response,
    responses={200: {"content": {"text/calendar": {}}}},
)
async def get_team_calendar(
    tournament_id: TournamentId,
    team_id: TeamId,
    _: UserPublic | None = Depends(user_authenticated_or_public_dashboard),
) -> Response:
    """The matches of a team as a calendar feed (iCalendar), for calendar apps."""
    return Response(
        content=await team_calendar(tournament_id, team_id, datetime_utc.now()),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="team-{team_id}.ics"'},
    )
