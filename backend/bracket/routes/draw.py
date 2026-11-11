from fastapi import APIRouter, Depends

from bracket.config import config
from bracket.logic.scheduling.stage_draw import DrawBody, draw_stage
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import user_authenticated_for_tournament
from bracket.routes.models import DrawResponse
from bracket.routes.util import disallow_archived_tournament
from bracket.utils.id_types import StageId, TournamentId

router = APIRouter(prefix=config.api_prefix)


@router.post("/tournaments/{tournament_id}/stages/{stage_id}/draw", response_model=DrawResponse)
async def draw_teams_into_groups(
    tournament_id: TournamentId,
    stage_id: StageId,
    body: DrawBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> DrawResponse:
    """
    Group draw: places the teams of the pots in the empty slots of the groups of the stage.
    One team per pot per group, and teams of the same club apart where possible. Returns the
    placements in the order they were drawn, so the draw can be shown team by team.
    """
    return DrawResponse(data=await draw_stage(tournament_id, stage_id, body))
