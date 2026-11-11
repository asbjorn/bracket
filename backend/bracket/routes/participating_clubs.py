from fastapi import APIRouter, Depends

from bracket.config import config
from bracket.logic.participating_clubs import (
    create_participating_club,
    delete_participating_club,
    get_participating_clubs,
    update_participating_club,
)
from bracket.models.db.participating_club import (
    ParticipatingClubCreateBody,
    ParticipatingClubUpdateBody,
)
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import user_authenticated_for_tournament
from bracket.routes.models import (
    ParticipatingClubCreatedResponse,
    ParticipatingClubsResponse,
    SuccessResponse,
)
from bracket.routes.util import disallow_archived_tournament
from bracket.utils.id_types import ParticipatingClubId, TournamentId

router = APIRouter(prefix=config.api_prefix)


@router.get(
    "/tournaments/{tournament_id}/participating_clubs", response_model=ParticipatingClubsResponse
)
async def get_clubs_of_cup(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> ParticipatingClubsResponse:
    """The clubs taking part in the cup, with their teams."""
    return ParticipatingClubsResponse(data=await get_participating_clubs(tournament_id))


@router.post(
    "/tournaments/{tournament_id}/participating_clubs",
    response_model=ParticipatingClubCreatedResponse,
)
async def create_club_of_cup(
    tournament_id: TournamentId,
    body: ParticipatingClubCreateBody,
    user: UserPublic = Depends(user_authenticated_for_tournament),
    _: Tournament = Depends(disallow_archived_tournament),
) -> ParticipatingClubCreatedResponse:
    """
    Adds a club with its teams at once: new teams and/or existing teams without a club.
    """
    return ParticipatingClubCreatedResponse(
        data=await create_participating_club(tournament_id, body, user)
    )


@router.put(
    "/tournaments/{tournament_id}/participating_clubs/{club_id}", response_model=SuccessResponse
)
async def update_club_of_cup(
    tournament_id: TournamentId,
    club_id: ParticipatingClubId,
    body: ParticipatingClubUpdateBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    """Renames the club and sets exactly which teams belong to it."""
    await update_participating_club(tournament_id, club_id, body)
    return SuccessResponse()


@router.delete(
    "/tournaments/{tournament_id}/participating_clubs/{club_id}", response_model=SuccessResponse
)
async def delete_club_of_cup(
    tournament_id: TournamentId,
    club_id: ParticipatingClubId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    """Deletes the club; its teams stay, without a club."""
    await delete_participating_club(tournament_id, club_id)
    return SuccessResponse()
