from typing import Literal

from heliclockter import datetime_utc

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import CategoryId, StageId, TournamentId


class StageInsertable(BaseModelORM):
    tournament_id: TournamentId
    name: str
    created: datetime_utc
    is_active: bool
    category_id: CategoryId | None = None


class Stage(StageInsertable):
    id: StageId


class StageUpdateBody(BaseModelORM):
    name: str


class StageCreateBody(BaseModelORM):
    category_id: CategoryId | None = None


class StageActivateBody(BaseModelORM):
    direction: Literal["next", "previous"] = "next"
    # Stages are activated per age class, `None` is for stages without a class.
    category_id: CategoryId | None = None
