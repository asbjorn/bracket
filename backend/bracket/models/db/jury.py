from enum import auto
from typing import Annotated

from heliclockter import datetime_utc
from pydantic import BaseModel, StringConstraints

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import TournamentId
from bracket.utils.text import SingleLine
from bracket.utils.types import EnumAutoStr

# NFF: a cup jury has at least three members, at most one from each club
MIN_JURY_MEMBERS = 3
MAX_JURY_MEMBERS = 15

JuryText = Annotated[
    str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True), SingleLine
]
JuryPhone = Annotated[
    str, StringConstraints(min_length=1, max_length=30, strip_whitespace=True), SingleLine
]


class JuryRole(EnumAutoStr):
    CHAIR = auto()  # Juryleder
    MEMBER = auto()


class JuryWarning(EnumAutoStr):
    TOO_FEW_MEMBERS = auto()
    SAME_CLUB = auto()
    NO_CHAIR = auto()


class JuryMemberBody(BaseModelORM):
    name: JuryText
    club_name: JuryText | None = None
    phone: JuryPhone | None = None
    role: JuryRole = JuryRole.MEMBER


class JuryMember(JuryMemberBody):
    id: int
    tournament_id: TournamentId
    created: datetime_utc


def jury_warnings(members: list[JuryMember]) -> list[JuryWarning]:
    """Checks the NFF rules for a cup jury: at least three members, at most one per club."""
    warnings: list[JuryWarning] = []
    if len(members) < MIN_JURY_MEMBERS:
        warnings.append(JuryWarning.TOO_FEW_MEMBERS)
    clubs = [m.club_name.strip().casefold() for m in members if m.club_name]
    if len(clubs) != len(set(clubs)):
        warnings.append(JuryWarning.SAME_CLUB)
    if members and not any(member.role is JuryRole.CHAIR for member in members):
        warnings.append(JuryWarning.NO_CHAIR)
    return warnings


class JuryOverview(BaseModel):
    members: list[JuryMember]
    warnings: list[JuryWarning]
