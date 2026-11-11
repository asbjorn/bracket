from fastapi import APIRouter, Depends, HTTPException
from heliclockter import datetime_utc
from starlette import status

from bracket.config import config
from bracket.database import database
from bracket.logic.subscriptions import check_requirement
from bracket.models.db.court import (
    Court,
    CourtBody,
    CourtsMultiBody,
    CourtSplitBody,
    CourtToInsert,
)
from bracket.models.db.time_window import PlanningHours, TimeWindowsBody
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import (
    user_authenticated_for_tournament,
    user_authenticated_or_public_dashboard,
)
from bracket.routes.models import (
    CourtsResponse,
    PlanningHoursResponse,
    SingleCourtResponse,
    SuccessResponse,
    TimeWindowsResponse,
)
from bracket.routes.util import disallow_archived_tournament
from bracket.schema import courts
from bracket.sql.categories import get_category_by_id
from bracket.sql.courts import (
    get_all_courts_in_tournament,
    sql_create_courts,
    sql_delete_court,
    update_court,
)
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.time_windows import (
    get_own_time_windows,
    get_time_windows,
    sql_replace_time_windows,
)
from bracket.utils.db import fetch_one_parsed
from bracket.utils.id_types import CategoryId, CourtId, TournamentId
from bracket.utils.types import assert_some

router = APIRouter(prefix=config.api_prefix)


@router.get("/tournaments/{tournament_id}/courts", response_model=CourtsResponse)
async def get_courts(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_or_public_dashboard),
) -> CourtsResponse:
    return CourtsResponse(data=await get_all_courts_in_tournament(tournament_id))


@router.put("/tournaments/{tournament_id}/courts/{court_id}", response_model=SingleCourtResponse)
async def update_court_by_id(
    tournament_id: TournamentId,
    court_id: CourtId,
    court_body: CourtBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SingleCourtResponse:
    await update_court(
        tournament_id=tournament_id,
        court_id=court_id,
        court_body=court_body,
    )
    return SingleCourtResponse(
        data=assert_some(
            await fetch_one_parsed(
                database,
                Court,
                courts.select().where(
                    (courts.c.id == court_id) & (courts.c.tournament_id == tournament_id)
                ),
            )
        )
    )


@router.delete("/tournaments/{tournament_id}/courts/{court_id}", response_model=SuccessResponse)
async def delete_court(
    tournament_id: TournamentId,
    court_id: CourtId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    stages = await get_full_tournament_details(tournament_id, no_draft_rounds=False)
    # Deleting a full pitch deletes its parts as well
    court_ids = {court_id} | {
        court.id
        for court in await get_all_courts_in_tournament(tournament_id)
        if court.parent_court_id == court_id
    }
    used_in_matches_count = 0
    for stage in stages:
        for stage_item in stage.stage_items:
            for round_ in stage_item.rounds:
                for match in round_.matches:
                    if match.court_id in court_ids:
                        used_in_matches_count += 1

    if used_in_matches_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not delete court since it's used by {used_in_matches_count} matches",
        )

    await sql_delete_court(tournament_id, court_id)
    return SuccessResponse()


@router.post("/tournaments/{tournament_id}/courts", response_model=SingleCourtResponse)
async def create_court(
    court_body: CourtBody,
    tournament_id: TournamentId,
    user: UserPublic = Depends(user_authenticated_for_tournament),
    _: Tournament = Depends(disallow_archived_tournament),
) -> SingleCourtResponse:
    existing_courts = await get_all_courts_in_tournament(tournament_id)
    check_requirement(existing_courts, user, "max_courts")

    last_record_id = await database.execute(
        query=courts.insert(),
        values=CourtToInsert(
            **court_body.model_dump(),
            created=datetime_utc.now(),
            tournament_id=tournament_id,
        ).model_dump(),
    )
    return SingleCourtResponse(
        data=assert_some(
            await fetch_one_parsed(
                database,
                Court,
                courts.select().where(
                    (courts.c.id == last_record_id) & (courts.c.tournament_id == tournament_id)
                ),
            )
        )
    )


@router.post("/tournaments/{tournament_id}/courts_multi", response_model=CourtsResponse)
async def create_multiple_courts(
    body: CourtsMultiBody,
    tournament_id: TournamentId,
    user: UserPublic = Depends(user_authenticated_for_tournament),
    _: Tournament = Depends(disallow_archived_tournament),
) -> CourtsResponse:
    """
    Creates `count` courts named "<name_prefix> 1", "<name_prefix> 2", etc.
    """
    existing_courts = await get_all_courts_in_tournament(tournament_id)
    check_requirement(existing_courts, user, "max_courts", additions=body.total_courts)
    await sql_create_courts(tournament_id, body)
    return CourtsResponse(data=await get_all_courts_in_tournament(tournament_id))


@router.get("/tournaments/{tournament_id}/time_windows", response_model=TimeWindowsResponse)
async def get_tournament_time_windows(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> TimeWindowsResponse:
    return TimeWindowsResponse(data=await get_time_windows(tournament_id))


@router.put("/tournaments/{tournament_id}/time_windows", response_model=TimeWindowsResponse)
async def replace_tournament_time_windows(
    body: TimeWindowsBody,
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> TimeWindowsResponse:
    """
    Sets the periods in which matches can be played, replacing the existing ones.
    """
    await sql_replace_time_windows(tournament_id, body.time_windows)
    return TimeWindowsResponse(data=await get_time_windows(tournament_id))


async def get_court_of_tournament(tournament_id: TournamentId, court_id: CourtId) -> Court:
    court = next(
        (c for c in await get_all_courts_in_tournament(tournament_id) if c.id == court_id), None
    )
    if court is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the court")
    return court


@router.post("/tournaments/{tournament_id}/courts/{court_id}/split", response_model=CourtsResponse)
async def split_court(
    tournament_id: TournamentId,
    court_id: CourtId,
    body: CourtSplitBody,
    user: UserPublic = Depends(user_authenticated_for_tournament),
    _: Tournament = Depends(disallow_archived_tournament),
) -> CourtsResponse:
    """
    Splits a full pitch into 2-4 parts named after it ("Bane 1A", "Bane 1B", ...). A match on
    the full pitch blocks its parts and a match on a part blocks the full pitch.
    """
    existing_courts = await get_all_courts_in_tournament(tournament_id)
    court = await get_court_of_tournament(tournament_id, court_id)
    if court.parent_court_id is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A part of a pitch can't be split again")
    if any(other.parent_court_id == court_id for other in existing_courts):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This pitch is already split")
    check_requirement(existing_courts, user, "max_courts", additions=body.parts)
    async with database.transaction():
        for letter in "ABCD"[: body.parts]:
            await database.execute(
                query=courts.insert(),
                values=CourtToInsert(
                    name=f"{court.name}{letter}",
                    game_format=body.game_format,
                    created=datetime_utc.now(),
                    tournament_id=tournament_id,
                ).model_dump()
                | {"parent_court_id": court_id},
            )
    return CourtsResponse(data=await get_all_courts_in_tournament(tournament_id))


@router.get("/tournaments/{tournament_id}/planning_hours", response_model=PlanningHoursResponse)
async def get_planning_hours(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> PlanningHoursResponse:
    """The opening hours of pitches and the days/hours of classes that have their own."""
    per_court, per_category = await get_own_time_windows(tournament_id)
    return PlanningHoursResponse(data=PlanningHours(courts=per_court, categories=per_category))


@router.put(
    "/tournaments/{tournament_id}/courts/{court_id}/time_windows", response_model=SuccessResponse
)
async def replace_court_time_windows(
    tournament_id: TournamentId,
    court_id: CourtId,
    body: TimeWindowsBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    """The opening hours of one pitch; empty: the playing hours of the cup."""
    await get_court_of_tournament(tournament_id, court_id)
    await sql_replace_time_windows(tournament_id, body.time_windows, court_id=court_id)
    return SuccessResponse()


@router.put(
    "/tournaments/{tournament_id}/categories/{category_id}/time_windows",
    response_model=SuccessResponse,
)
async def replace_category_time_windows(
    tournament_id: TournamentId,
    category_id: CategoryId,
    body: TimeWindowsBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    """The days and hours a class plays; empty: whenever the cup plays."""
    if await get_category_by_id(tournament_id, category_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the class")
    await sql_replace_time_windows(tournament_id, body.time_windows, category_id=category_id)
    return SuccessResponse()
