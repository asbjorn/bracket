from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from bracket.config import config
from bracket.logic.planning.capacity import CapacityBody, calculate_capacity
from bracket.models.db.user import UserPublic
from bracket.routes.auth import user_authenticated
from bracket.routes.models import CapacityResponse

router = APIRouter(prefix=config.api_prefix)


@router.post("/capacity", response_model=CapacityResponse)
async def calculate_cup_capacity(
    body: CapacityBody,
    _: UserPublic = Depends(user_authenticated),
) -> CapacityResponse:
    """
    What-if for a cup that doesn't exist yet: do these classes fit on these courts within these
    playing hours? Plans the resulting matches with the real scheduler and tells what's missing.
    """
    # CPU-bound: don't block other requests while planning
    return CapacityResponse(data=await run_in_threadpool(calculate_capacity, body))
