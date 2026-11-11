from enum import auto
from typing import Annotated, Self

from heliclockter import datetime_utc
from pydantic import BaseModel, EmailStr, Field, StringConstraints, model_validator

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import CourtHostId, CourtId, MatchId, OfficialId, TournamentId
from bracket.utils.types import EnumAutoStr

Text50 = Annotated[str, StringConstraints(min_length=1, max_length=50, strip_whitespace=True)]
Phone = Annotated[str, StringConstraints(min_length=1, max_length=30, strip_whitespace=True)]
MAX_FEE = 100_000


class OfficialRole(EnumAutoStr):
    REFEREE = auto()
    HOST = auto()  # Kampvert


class MatchOfficialRole(EnumAutoStr):
    REFEREE = auto()
    ASSISTANT = auto()


class OfficialBody(BaseModelORM):
    name: Text50
    age: int | None = Field(None, ge=8, le=99)
    # E.g. "Rekrutteringsdommer", "Klubbdommer", "Kretsdommer"
    level: Text50 | None = None
    club_name: Text50 | None = None
    phone: Phone | None = None
    email: EmailStr | None = None
    role: OfficialRole = OfficialRole.REFEREE
    fee_per_match: int = Field(0, ge=0, le=MAX_FEE)
    fee_per_day: int = Field(0, ge=0, le=MAX_FEE)
    active: bool = True


class Official(OfficialBody):
    """Only for the organiser: it has phone and email."""

    id: OfficialId
    tournament_id: TournamentId
    created: datetime_utc
    email: str | None = None  # pyrefly: ignore [bad-override]


class MatchOfficial(BaseModelORM):
    match_id: MatchId
    official_id: OfficialId
    role: MatchOfficialRole


class MatchOfficialsBody(BaseModel):
    """Replaces who refs the match."""

    referee_id: OfficialId | None = None
    assistant_ids: list[OfficialId] = Field(default=[], max_length=4)

    @model_validator(mode="after")
    def check_distinct(self) -> Self:
        ids = [*self.assistant_ids, *([self.referee_id] if self.referee_id is not None else [])]
        if len(ids) != len(set(ids)):
            raise ValueError("An official can only have one role in a match")
        return self


class BlockAssignmentBody(BaseModel):
    """All scheduled matches on a court that start in [start_time, end_time) get this referee."""

    official_id: OfficialId
    court_id: CourtId
    start_time: datetime_utc
    end_time: datetime_utc

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("The end must be after the start")
        return self


class CourtHostBody(BlockAssignmentBody):
    pass


class CourtHost(CourtHostBody):
    id: CourtHostId
    tournament_id: TournamentId


class OfficialConflictKind(EnumAutoStr):
    DOUBLE_BOOKED = auto()
    OWN_CLUB = auto()
    INACTIVE = auto()


class OfficialConflict(BaseModel):
    official_id: OfficialId
    kind: OfficialConflictKind
    match_id: MatchId | None = None
    # The other match (or host block) of a double booking
    other_match_id: MatchId | None = None
    court_host_id: CourtHostId | None = None


class OfficialFee(BaseModel):
    official_id: OfficialId
    name: str
    matches: int
    days: int
    host_days: int
    total: int


class OfficialsOverview(BaseModel):
    officials: list[Official]
    assignments: list[MatchOfficial]
    hosts: list[CourtHost]
    conflicts: list[OfficialConflict]
    fees: list[OfficialFee]


class PublicMatchOfficial(BaseModel):
    """What the public, the pitch and printed cards may see: the name only."""

    match_id: MatchId
    name: str
    role: MatchOfficialRole
