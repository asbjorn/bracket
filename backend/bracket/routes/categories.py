from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from bracket.config import config
from bracket.logic.results_visibility import check_category_can_hide_results
from bracket.logic.subscriptions import check_requirement
from bracket.models.db.category import CategoryBody
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import (
    user_authenticated_for_tournament,
    user_authenticated_or_public_dashboard,
)
from bracket.routes.models import CategoriesResponse, SingleCategoryResponse, SuccessResponse
from bracket.routes.util import disallow_archived_tournament
from bracket.sql.categories import (
    get_all_categories_in_tournament,
    get_category_by_id,
    sql_create_category,
    sql_delete_category,
    sql_update_category,
)
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.errors import (
    ForeignKey,
    UniqueIndex,
    check_foreign_key_violation,
    check_unique_constraint_violation,
)
from bracket.utils.id_types import CategoryId, TournamentId

router = APIRouter(prefix=config.api_prefix)


def raise_category_not_found(category_id: CategoryId) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Could not find class with id {category_id}",
    )


@router.get("/tournaments/{tournament_id}/categories", response_model=CategoriesResponse)
async def get_categories(
    tournament_id: TournamentId,
    _: UserPublic | None = Depends(user_authenticated_or_public_dashboard),
) -> CategoriesResponse:
    return CategoriesResponse(data=await get_all_categories_in_tournament(tournament_id))


@router.post("/tournaments/{tournament_id}/categories", response_model=SingleCategoryResponse)
async def create_category(
    tournament_id: TournamentId,
    category_body: CategoryBody,
    user: UserPublic = Depends(user_authenticated_for_tournament),
    _: Tournament = Depends(disallow_archived_tournament),
) -> SingleCategoryResponse:
    existing_categories = await get_all_categories_in_tournament(tournament_id)
    check_requirement(existing_categories, user, "max_categories")

    with check_unique_constraint_violation({UniqueIndex.categories_tournament_id_name_key}):
        category = await sql_create_category(tournament_id, category_body)
    return SingleCategoryResponse(data=category)


@router.put(
    "/tournaments/{tournament_id}/categories/{category_id}",
    response_model=SingleCategoryResponse,
)
async def update_category(
    tournament_id: TournamentId,
    category_id: CategoryId,
    category_body: CategoryBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SingleCategoryResponse:
    if not category_body.get_results_public():
        stages = await get_full_tournament_details(tournament_id)
        check_category_can_hide_results(stages, category_id)

    with check_unique_constraint_violation({UniqueIndex.categories_tournament_id_name_key}):
        category = await sql_update_category(tournament_id, category_id, category_body)

    if category is None:
        raise_category_not_found(category_id)

    return SingleCategoryResponse(data=category)


@router.delete(
    "/tournaments/{tournament_id}/categories/{category_id}", response_model=SuccessResponse
)
async def delete_category(
    tournament_id: TournamentId,
    category_id: CategoryId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    if await get_category_by_id(tournament_id, category_id) is None:
        raise_category_not_found(category_id)

    with check_foreign_key_violation(
        {ForeignKey.stages_category_id_fkey, ForeignKey.teams_category_id_fkey}
    ):
        await sql_delete_category(tournament_id, category_id)

    return SuccessResponse()
