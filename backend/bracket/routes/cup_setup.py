from fastapi import APIRouter, Depends

from bracket.config import config
from bracket.logic.scheduling.cup_setup import CupSetupBody, set_up_cup
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import user_authenticated_for_tournament
from bracket.routes.models import SuccessResponse
from bracket.routes.util import disallow_archived_tournament
from bracket.utils.id_types import TournamentId

router = APIRouter(prefix=config.api_prefix)


@router.post("/tournaments/{tournament_id}/cup_setup", response_model=SuccessResponse)
async def create_cup_structure(
    tournament_id: TournamentId,
    body: CupSetupBody,
    user: UserPublic = Depends(user_authenticated_for_tournament),
    _: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    """
    Setup wizard: creates the classes, their group stages and playoffs, the courts and the
    playing hours of a new cup at once. Teams are drawn into the groups afterwards.
    """
    await set_up_cup(tournament_id, body, user)
    return SuccessResponse()
