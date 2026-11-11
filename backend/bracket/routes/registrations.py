from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from heliclockter import datetime_utc
from starlette import status

from bracket.config import config
from bracket.logic.registration import (
    get_open_classes,
    get_registrations,
    promote_from_waitlist,
    register_team,
    registrations_csv,
    set_entry_fees,
    set_registration_settings,
    update_registration,
)
from bracket.models.db.registration import (
    EntryFeeBody,
    PublicRegistrationBody,
    PublicRegistrationResult,
    RegistrationSettingsBody,
    RegistrationUpdateBody,
)
from bracket.models.db.team import RegistrationStatus
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import (
    user_authenticated_for_tournament,
    user_authenticated_or_public_dashboard,
)
from bracket.routes.models import (
    PublicRegistrationClassesResponse,
    PublicRegistrationResponse,
    RegistrationsResponse,
    SuccessResponse,
)
from bracket.routes.util import disallow_archived_tournament
from bracket.sql.categories import get_all_categories_in_tournament
from bracket.utils.id_types import CategoryId, TeamId, TournamentId
from bracket.utils.rate_limit import SlidingWindowLimiter

router = APIRouter(prefix=config.api_prefix)

# Per client: a club signs up a handful of teams, a bot many
public_sign_ups = SlidingWindowLimiter(limit=10, window_seconds=3600)


@router.get(
    "/tournaments/{tournament_id}/registration/classes",
    response_model=PublicRegistrationClassesResponse,
)
async def get_classes_open_for_registration(
    tournament_id: TournamentId,
    _: UserPublic | None = Depends(user_authenticated_or_public_dashboard),
) -> PublicRegistrationClassesResponse:
    """The classes that teams can sign up for now, with the spots left."""
    return PublicRegistrationClassesResponse(
        data=await get_open_classes(tournament_id, datetime_utc.now())
    )


@router.post("/tournaments/{tournament_id}/registration", response_model=PublicRegistrationResponse)
async def register_team_publicly(
    tournament_id: TournamentId,
    body: PublicRegistrationBody,
    request: Request,
    _: UserPublic | None = Depends(user_authenticated_or_public_dashboard),
) -> PublicRegistrationResponse:
    """
    Public sign-up of a team (only for a public cup, an open class and before the deadline).
    When the class is full, the team goes to the waitlist.
    """
    client = request.client.host if request.client is not None else "unknown"
    public_sign_ups.check(f"{tournament_id}:{client}")
    if body.website != "":
        # A bot filled in the hidden field: pretend it worked, store nothing
        return PublicRegistrationResponse(
            data=PublicRegistrationResult(
                team_name=body.team_name,
                registration_status=RegistrationStatus.REGISTERED,
                waitlist_place=None,
            )
        )
    return PublicRegistrationResponse(
        data=await register_team(tournament_id, body, datetime_utc.now())
    )


@router.get("/tournaments/{tournament_id}/registrations", response_model=RegistrationsResponse)
async def get_tournament_registrations(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> RegistrationsResponse:
    """All teams with their registration, including contact details (organiser only)."""
    return RegistrationsResponse(data=await get_registrations(tournament_id))


@router.get("/tournaments/{tournament_id}/registrations.csv")
async def export_tournament_registrations(
    tournament_id: TournamentId,
    language: str = "en",
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> Response:
    content = registrations_csv(
        await get_registrations(tournament_id),
        await get_all_categories_in_tournament(tournament_id),
        language,
    )
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="registrations.csv"'},
    )


@router.put("/tournaments/{tournament_id}/registrations/{team_id}", response_model=SuccessResponse)
async def update_team_registration(
    tournament_id: TournamentId,
    team_id: TeamId,
    body: RegistrationUpdateBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    await update_registration(tournament_id, team_id, body)
    return SuccessResponse()


@router.post(
    "/tournaments/{tournament_id}/categories/{category_id}/waitlist/promote",
    response_model=SuccessResponse,
)
async def promote_first_on_waitlist(
    tournament_id: TournamentId,
    category_id: CategoryId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    await promote_from_waitlist(tournament_id, category_id)
    return SuccessResponse()


@router.put(
    "/tournaments/{tournament_id}/categories/{category_id}/registration",
    response_model=SuccessResponse,
)
async def update_registration_settings(
    tournament_id: TournamentId,
    category_id: CategoryId,
    body: RegistrationSettingsBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    if not await set_registration_settings(tournament_id, category_id, body):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the class")
    return SuccessResponse()


@router.put("/tournaments/{tournament_id}/entry_fees", response_model=SuccessResponse)
async def update_entry_fees(
    tournament_id: TournamentId,
    body: EntryFeeBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    await set_entry_fees(tournament_id, body)
    return SuccessResponse()
