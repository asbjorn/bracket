from __future__ import annotations

import json
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from heliclockter import datetime_utc
from pydantic import BaseModel, Field, StringConstraints, field_validator

from bracket.logic.ranking.statistics import START_ELO
from bracket.models.db.player import Player
from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import (
    CategoryId,
    ParticipatingClubId,
    PlayerId,
    TeamId,
    TournamentId,
)
from bracket.utils.text import SingleLine


class RegistrationStatus(StrEnum):
    """
    Teams created by the organiser are APPROVED. Teams that sign up themselves are REGISTERED,
    or on the WAITLIST when their class is full. Both APPROVED and REGISTERED teams take part.
    """

    APPROVED = "APPROVED"
    REGISTERED = "REGISTERED"
    WAITLIST = "WAITLIST"
    REJECTED = "REJECTED"

    @property
    def participates(self) -> bool:
        return self in PARTICIPATING_STATUSES


PARTICIPATING_STATUSES = frozenset({RegistrationStatus.APPROVED, RegistrationStatus.REGISTERED})


class TeamInsertable(BaseModelORM):
    created: datetime_utc
    name: str
    tournament_id: TournamentId
    active: bool
    elo_score: Decimal = START_ELO
    swiss_score: Decimal = Decimal("0.0")
    wins: int = 0
    draws: int = 0
    losses: int = 0
    logo_path: str | None = None
    category_id: CategoryId | None = None
    club_id: ParticipatingClubId | None = None
    squad_size: int | None = None
    withdrawn: bool = False
    checked_in: bool = False
    registration_status: RegistrationStatus = RegistrationStatus.APPROVED


class Team(TeamInsertable):
    id: TeamId


class TeamWithPlayers(BaseModel):
    id: TeamId
    players: list[Player]
    elo_score: Decimal = START_ELO
    swiss_score: Decimal = Decimal("0.0")
    wins: int = 0
    draws: int = 0
    losses: int = 0
    name: str
    logo_path: str | None = None
    category_id: CategoryId | None = None
    club_id: ParticipatingClubId | None = None
    squad_size: int | None = None
    withdrawn: bool = False
    checked_in: bool = False
    registration_status: RegistrationStatus = RegistrationStatus.APPROVED

    @property
    def player_ids(self) -> list[PlayerId]:
        return [player.id for player in self.players]

    @field_validator("players", mode="before")
    @staticmethod
    def handle_players(values: list[Player]) -> list[Player]:
        if isinstance(values, str):
            values_json = json.loads(values)
            if values_json == [None]:
                return []
            return values_json

        return values


class FullTeamWithPlayers(TeamWithPlayers, Team):
    pass


ClubName = Annotated[
    str, StringConstraints(min_length=1, max_length=50, strip_whitespace=True), SingleLine
]


MAX_SQUAD_SIZE = 60
# Room for a club name (max 50) plus class and number, e.g. "Sandnes IL G9 2"
MAX_TEAM_NAME_LENGTH = 50
TeamName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_TEAM_NAME_LENGTH, strip_whitespace=True),
    SingleLine,
]


class TeamBody(BaseModelORM):
    name: TeamName
    active: bool
    player_ids: set[PlayerId]
    category_id: CategoryId | None = None
    # Empty: the draw takes the club from the name without a trailing number ("Brann 2" -> Brann)
    club_id: ParticipatingClubId | None = None
    # Players in the squad (e.g. for counting medals)
    squad_size: int | None = Field(default=None, ge=1, le=MAX_SQUAD_SIZE)


class TeamMultiBody(BaseModelORM):
    names: str = Field(..., min_length=1)
    active: bool
    category_id: CategoryId | None = None


class TeamConflict(BaseModel):
    """Two teams that must never play at the same time (they share coaches or players)."""

    team1_id: TeamId
    team2_id: TeamId


class TeamConflictsBody(BaseModel):
    """Exactly the teams that can't play at the same time as this team."""

    team_ids: list[TeamId] = Field(default=[], max_length=50)
