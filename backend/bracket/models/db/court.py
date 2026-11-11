from heliclockter import datetime_utc
from pydantic import Field

from bracket.models.db.game_format import GameFormat
from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import CourtId, TournamentId


class CourtInsertable(BaseModelORM):
    name: str
    created: datetime_utc
    tournament_id: TournamentId
    # Courts without a format can be used for any class
    game_format: GameFormat | None = None


class Court(CourtInsertable):
    id: CourtId


class CourtBody(BaseModelORM):
    name: str
    game_format: GameFormat | None = None


class CourtsMultiBody(BaseModelORM):
    """Creates courts "<name_prefix> 1", "<name_prefix> 2", ... continuing the numbering."""

    count: int = Field(ge=1, le=32)
    name_prefix: str = Field("Court", min_length=1, max_length=40)
    game_format: GameFormat | None = None


class CourtToInsert(CourtBody):
    created: datetime_utc
    tournament_id: TournamentId
