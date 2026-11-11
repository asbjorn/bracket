from fastapi import APIRouter, Depends

from bracket.config import config
from bracket.logic.district_application import get_district_application, set_details
from bracket.models.db.district_application import TournamentDetails
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import user_authenticated_for_tournament
from bracket.routes.models import DistrictApplicationResponse, SuccessResponse
from bracket.routes.util import disallow_archived_tournament
from bracket.utils.id_types import TournamentId

router = APIRouter(prefix=config.api_prefix)


@router.get(
    "/tournaments/{tournament_id}/district_application",
    response_model=DistrictApplicationResponse,
)
async def get_tournament_district_application(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> DistrictApplicationResponse:
    """
    Summary of the cup for the application to the district (krets): playing days, courts,
    classes, teams and matches, plus the facts entered by the organiser. Organiser only.
    """
    return DistrictApplicationResponse(data=await get_district_application(tournament_id))


@router.put("/tournaments/{tournament_id}/details", response_model=SuccessResponse)
async def update_tournament_details(
    tournament_id: TournamentId,
    body: TournamentDetails,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    await set_details(tournament_id, body)
    return SuccessResponse()
