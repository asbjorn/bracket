from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from bracket.config import config
from bracket.logic.discipline_service import (
    check_card,
    check_jury_decision,
    get_discipline_overview,
)
from bracket.models.db.discipline import DisciplineSettingsBody, JuryDecisionBody, MatchCardBody
from bracket.models.db.jury import MAX_JURY_MEMBERS, JuryMemberBody, JuryOverview, jury_warnings
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import user_authenticated_for_tournament
from bracket.routes.models import (
    DisciplineOverviewResponse,
    JuryMembersResponse,
    MatchCardResponse,
    SuccessResponse,
)
from bracket.routes.util import disallow_archived_tournament
from bracket.sql.discipline import (
    sql_create_card,
    sql_create_jury_decision,
    sql_delete_card,
    sql_delete_jury_decision,
    sql_set_discipline_settings,
)
from bracket.sql.jury import (
    get_jury_members,
    sql_create_jury_member,
    sql_delete_jury_member,
    sql_update_jury_member,
)
from bracket.utils.id_types import JuryDecisionId, MatchCardId, MatchId, TournamentId

router = APIRouter(prefix=config.api_prefix)


@router.get("/tournaments/{tournament_id}/discipline", response_model=DisciplineOverviewResponse)
async def get_tournament_discipline(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> DisciplineOverviewResponse:
    """Cards, the suspensions that follow from them, the settings and the jury's log."""
    return DisciplineOverviewResponse(data=await get_discipline_overview(tournament_id))


@router.put("/tournaments/{tournament_id}/discipline_settings", response_model=SuccessResponse)
async def update_discipline_settings(
    tournament_id: TournamentId,
    body: DisciplineSettingsBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    await sql_set_discipline_settings(tournament_id, body)
    return SuccessResponse()


@router.post(
    "/tournaments/{tournament_id}/matches/{match_id}/cards", response_model=MatchCardResponse
)
async def create_match_card(
    tournament_id: TournamentId,
    match_id: MatchId,
    body: MatchCardBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> MatchCardResponse:
    await check_card(tournament_id, match_id, body)
    return MatchCardResponse(data=await sql_create_card(tournament_id, match_id, body))


@router.delete("/tournaments/{tournament_id}/cards/{card_id}", response_model=SuccessResponse)
async def delete_match_card(
    tournament_id: TournamentId,
    card_id: MatchCardId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    if not await sql_delete_card(tournament_id, card_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the card")
    return SuccessResponse()


@router.post("/tournaments/{tournament_id}/jury_decisions", response_model=SuccessResponse)
async def create_jury_decision(
    tournament_id: TournamentId,
    body: JuryDecisionBody,
    user: UserPublic = Depends(user_authenticated_for_tournament),
    _: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    """Logs a decision of the jury; with a card, it can add or remove suspended matches."""
    await check_jury_decision(tournament_id, body)
    await sql_create_jury_decision(tournament_id, body, user.id)
    return SuccessResponse()


@router.delete(
    "/tournaments/{tournament_id}/jury_decisions/{decision_id}", response_model=SuccessResponse
)
async def delete_jury_decision(
    tournament_id: TournamentId,
    decision_id: JuryDecisionId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    if not await sql_delete_jury_decision(tournament_id, decision_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the decision")
    return SuccessResponse()


@router.get("/tournaments/{tournament_id}/jury_members", response_model=JuryMembersResponse)
async def get_tournament_jury_members(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> JuryMembersResponse:
    """The cup's jury, with warnings for the NFF rules (at least 3, at most one per club)."""
    members = await get_jury_members(tournament_id)
    return JuryMembersResponse(data=JuryOverview(members=members, warnings=jury_warnings(members)))


@router.post("/tournaments/{tournament_id}/jury_members", response_model=SuccessResponse)
async def create_jury_member(
    tournament_id: TournamentId,
    body: JuryMemberBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    if len(await get_jury_members(tournament_id)) >= MAX_JURY_MEMBERS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The jury is full")
    await sql_create_jury_member(tournament_id, body)
    return SuccessResponse()


@router.put("/tournaments/{tournament_id}/jury_members/{member_id}", response_model=SuccessResponse)
async def update_jury_member(
    tournament_id: TournamentId,
    member_id: int,
    body: JuryMemberBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    if not await sql_update_jury_member(tournament_id, member_id, body):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the jury member")
    return SuccessResponse()


@router.delete(
    "/tournaments/{tournament_id}/jury_members/{member_id}", response_model=SuccessResponse
)
async def delete_jury_member(
    tournament_id: TournamentId,
    member_id: int,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    if not await sql_delete_jury_member(tournament_id, member_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the jury member")
    return SuccessResponse()
