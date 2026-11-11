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
    # A part of a split pitch: the full pitch it belongs to
    parent_court_id: CourtId | None = None


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
    # Each court is a full pitch split into this many parts (e.g. two 7v7 halves)
    split_into: int | None = Field(None, ge=2, le=4)
    part_format: GameFormat | None = None

    @property
    def total_courts(self) -> int:
        return self.count * (1 + (self.split_into or 0))


class CourtToInsert(CourtBody):
    created: datetime_utc
    tournament_id: TournamentId


class CourtSplitBody(BaseModelORM):
    """Splits a full pitch into parts, e.g. an 11v11 pitch into two 7v7 halves "Bane 1A/1B"."""

    parts: int = Field(ge=2, le=4)
    game_format: GameFormat | None = None
