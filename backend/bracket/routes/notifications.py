from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from bracket.config import config
from bracket.logic.notifications import (
    NotificationSettingsBody,
    get_notification_status,
    queue_announcement,
    queue_schedule_notices,
    set_language,
)
from bracket.logic.public_info import get_announcement
from bracket.models.db.account import UserAccountType
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import user_authenticated_for_tournament
from bracket.routes.models import (
    NotificationsQueuedResponse,
    NotificationStatusResponse,
    ScheduleNoticeResponse,
    SuccessResponse,
)
from bracket.routes.util import disallow_archived_tournament
from bracket.utils.email import get_email_sender
from bracket.utils.id_types import TournamentId
from bracket.utils.rate_limit import RateLimiter

router = APIRouter(prefix=config.api_prefix)

# Sending to all teams at once: at most 20 times an hour per tournament, 50 a day per user
bulk_sends = RateLimiter("bulk_sends", limit=20, window_seconds=3600)
bulk_sends_per_user = RateLimiter("bulk_sends_per_user", limit=50, window_seconds=24 * 3600)


async def check_can_send(tournament_id: TournamentId, user: UserPublic) -> None:
    if get_email_sender() is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email is not set up on this server")
    if user.account_type == UserAccountType.DEMO:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Demo accounts can't send emails")
    await bulk_sends.check(str(tournament_id))
    await bulk_sends_per_user.check(str(user.id))


@router.get("/tournaments/{tournament_id}/notifications", response_model=NotificationStatusResponse)
async def get_tournament_notifications(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> NotificationStatusResponse:
    """Whether email is set up, the language, and the emails sent to team contacts."""
    return NotificationStatusResponse(data=await get_notification_status(tournament_id))


@router.put("/tournaments/{tournament_id}/notification_settings", response_model=SuccessResponse)
async def update_notification_settings(
    tournament_id: TournamentId,
    body: NotificationSettingsBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    await set_language(tournament_id, body.language)
    return SuccessResponse()


@router.post(
    "/tournaments/{tournament_id}/notifications/announcement",
    response_model=NotificationsQueuedResponse,
)
async def email_announcement(
    tournament_id: TournamentId,
    user: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> NotificationsQueuedResponse:
    """Emails the current announcement to the contacts of all teams (once per text and team)."""
    announcement = await get_announcement(tournament_id)
    if announcement is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "There is no announcement to send")
    await check_can_send(tournament_id, user)
    return NotificationsQueuedResponse(
        data=await queue_announcement(tournament_id, announcement.text)
    )


@router.post(
    "/tournaments/{tournament_id}/notifications/schedule", response_model=ScheduleNoticeResponse
)
async def email_schedule_changes(
    tournament_id: TournamentId,
    dry_run: bool = False,
    user: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> ScheduleNoticeResponse:
    """
    Emails each team its next matches, only to teams whose times changed since their last
    notice. `dry_run` only counts them.
    """
    if not dry_run:
        await check_can_send(tournament_id, user)
    return ScheduleNoticeResponse(data=await queue_schedule_notices(tournament_id, dry_run=dry_run))
