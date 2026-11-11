from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from starlette import status

from bracket.config import config
from bracket.logic.officials import fee_summary, fees_csv, find_conflicts, matches_in_block
from bracket.models.db.official import (
    BlockAssignmentBody,
    CourtHostBody,
    MatchOfficialsBody,
    OfficialBody,
    OfficialsOverview,
)
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import (
    user_authenticated_for_tournament,
    user_authenticated_or_public_dashboard,
)
from bracket.routes.models import (
    OfficialResponse,
    OfficialsOverviewResponse,
    PublicMatchOfficialsResponse,
    SuccessResponse,
)
from bracket.routes.util import disallow_archived_tournament
from bracket.sql.courts import get_all_courts_in_tournament
from bracket.sql.officials import (
    get_court_hosts,
    get_match_officials,
    get_match_slots,
    get_officials,
    get_public_match_officials,
    sql_create_court_host,
    sql_create_official,
    sql_delete_court_host,
    sql_delete_official,
    sql_replace_match_officials,
    sql_set_referee,
    sql_update_official,
)
from bracket.utils.errors import UniqueIndex, check_unique_constraint_violation
from bracket.utils.id_types import CourtHostId, CourtId, MatchId, OfficialId, TournamentId

router = APIRouter(prefix=config.api_prefix)


def not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"Could not find the {what}")


async def check_officials_exist(
    tournament_id: TournamentId, official_ids: list[OfficialId]
) -> None:
    known = {official.id for official in await get_officials(tournament_id)}
    if any(official_id not in known for official_id in official_ids):
        raise not_found("official")


async def check_court_exists(tournament_id: TournamentId, court_id: CourtId) -> None:
    if court_id not in {court.id for court in await get_all_courts_in_tournament(tournament_id)}:
        raise not_found("court")


async def get_overview(tournament_id: TournamentId) -> OfficialsOverview:
    officials = await get_officials(tournament_id)
    assignments = await get_match_officials(tournament_id)
    hosts = await get_court_hosts(tournament_id)
    slots = await get_match_slots(tournament_id)
    return OfficialsOverview(
        officials=officials,
        assignments=assignments,
        hosts=hosts,
        conflicts=find_conflicts(officials, assignments, slots, hosts),
        fees=fee_summary(officials, assignments, slots, hosts),
    )


@router.get("/tournaments/{tournament_id}/officials", response_model=OfficialsOverviewResponse)
async def get_tournament_officials(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> OfficialsOverviewResponse:
    """Officials with contact details, their matches and host blocks, conflicts and fees."""
    return OfficialsOverviewResponse(data=await get_overview(tournament_id))


@router.post("/tournaments/{tournament_id}/officials", response_model=OfficialResponse)
async def create_official(
    tournament_id: TournamentId,
    body: OfficialBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> OfficialResponse:
    return OfficialResponse(data=await sql_create_official(tournament_id, body))


@router.put("/tournaments/{tournament_id}/officials/{official_id}", response_model=SuccessResponse)
async def update_official(
    tournament_id: TournamentId,
    official_id: OfficialId,
    body: OfficialBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    if not await sql_update_official(tournament_id, official_id, body):
        raise not_found("official")
    return SuccessResponse()


@router.delete(
    "/tournaments/{tournament_id}/officials/{official_id}", response_model=SuccessResponse
)
async def delete_official(
    tournament_id: TournamentId,
    official_id: OfficialId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    """Also removes the official from their matches and host blocks."""
    if not await sql_delete_official(tournament_id, official_id):
        raise not_found("official")
    return SuccessResponse()


@router.put(
    "/tournaments/{tournament_id}/matches/{match_id}/officials", response_model=SuccessResponse
)
async def set_match_officials(
    tournament_id: TournamentId,
    match_id: MatchId,
    body: MatchOfficialsBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    """Sets the referee and assistants of a match (replacing the current ones)."""
    if match_id not in await get_match_slots(tournament_id):
        raise not_found("match")
    referee = [body.referee_id] if body.referee_id is not None else []
    await check_officials_exist(tournament_id, [*referee, *body.assistant_ids])
    with check_unique_constraint_violation(
        {
            UniqueIndex.ix_match_officials_one_referee,
            UniqueIndex.match_officials_match_id_official_id_key,
        }
    ):
        await sql_replace_match_officials(match_id, body.referee_id, body.assistant_ids)
    return SuccessResponse()


@router.post("/tournaments/{tournament_id}/officials/assign_block", response_model=SuccessResponse)
async def assign_referee_to_block(
    tournament_id: TournamentId,
    body: BlockAssignmentBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    """The official referees every match on the court that starts in the period."""
    await check_officials_exist(tournament_id, [body.official_id])
    await check_court_exists(tournament_id, body.court_id)
    match_ids = matches_in_block(
        await get_match_slots(tournament_id), body.court_id, body.start_time, body.end_time
    )
    if len(match_ids) < 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No matches on this court in this period")
    await sql_set_referee(match_ids, body.official_id)
    return SuccessResponse()


@router.post("/tournaments/{tournament_id}/court_hosts", response_model=SuccessResponse)
async def create_court_host(
    tournament_id: TournamentId,
    body: CourtHostBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    """A match host (kampvert) for a court during a period."""
    await check_officials_exist(tournament_id, [body.official_id])
    await check_court_exists(tournament_id, body.court_id)
    await sql_create_court_host(tournament_id, body)
    return SuccessResponse()


@router.delete(
    "/tournaments/{tournament_id}/court_hosts/{court_host_id}", response_model=SuccessResponse
)
async def delete_court_host(
    tournament_id: TournamentId,
    court_host_id: CourtHostId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    if not await sql_delete_court_host(tournament_id, court_host_id):
        raise not_found("host block")
    return SuccessResponse()


@router.get("/tournaments/{tournament_id}/officials_fees.csv")
async def export_official_fees(
    tournament_id: TournamentId,
    language: str = "en",
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> Response:
    overview = await get_overview(tournament_id)
    return Response(
        content=fees_csv(overview.officials, overview.fees, language).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="officials-fees.csv"'},
    )


@router.get(
    "/tournaments/{tournament_id}/match_officials", response_model=PublicMatchOfficialsResponse
)
async def get_referees_of_matches(
    tournament_id: TournamentId,
    _: UserPublic | None = Depends(user_authenticated_or_public_dashboard),
) -> PublicMatchOfficialsResponse:
    """Who refs which match, by name only (no contact details): also for public pages."""
    return PublicMatchOfficialsResponse(data=await get_public_match_officials(tournament_id))
