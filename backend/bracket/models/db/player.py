from decimal import Decimal
from typing import Annotated

from heliclockter import datetime_utc
from pydantic import Field, StringConstraints

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import PlayerId, TournamentId
from bracket.utils.text import SingleLine

MAX_PLAYER_NAME_LENGTH = 100
PlayerName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_PLAYER_NAME_LENGTH, strip_whitespace=True),
    SingleLine,
]


class PlayerInsertable(BaseModelORM):
    active: bool
    name: str
    created: datetime_utc
    tournament_id: TournamentId
    elo_score: Decimal = Decimal("0.0")
    swiss_score: Decimal = Decimal("0.0")
    wins: int = 0
    draws: int = 0
    losses: int = 0


class Player(PlayerInsertable):
    id: PlayerId

    def __hash__(self) -> int:
        return self.id


class PlayerBody(BaseModelORM):
    name: PlayerName
    active: bool


class PlayerMultiBody(BaseModelORM):
    names: str = Field(..., min_length=1)
    active: bool


class PlayerToInsert(PlayerBody):
    created: datetime_utc
    tournament_id: TournamentId
    elo_score: Decimal = Decimal("1200.0")
    swiss_score: Decimal
    wins: int = 0
    draws: int = 0
    losses: int = 0
