from enum import auto

from heliclockter import datetime_utc
from pydantic import Field

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import ClubId, TournamentId
from bracket.utils.pydantic import EmptyStrToNone
from bracket.utils.types import EnumAutoStr


class TournamentStatus(EnumAutoStr):
    OPEN = auto()
    ARCHIVED = auto()


class TournamentInsertable(BaseModelORM):
    club_id: ClubId
    name: str
    created: datetime_utc
    start_time: datetime_utc
    duration_minutes: int = Field(..., ge=1)
    margin_minutes: int = Field(..., ge=0)
    min_rest_minutes: int = Field(default=0, ge=0)
    stage_buffer_minutes: int = Field(default=10, ge=0)
    dashboard_public: bool
    dashboard_endpoint: str | None = None
    logo_path: str | None = None
    players_can_be_in_multiple_teams: bool
    auto_assign_courts: bool
    status: TournamentStatus = TournamentStatus.OPEN


class Tournament(TournamentInsertable):
    id: TournamentId


class TournamentUpdateBody(BaseModelORM):
    start_time: datetime_utc
    name: str
    dashboard_public: bool
    dashboard_endpoint: EmptyStrToNone | str = None
    players_can_be_in_multiple_teams: bool
    auto_assign_courts: bool
    duration_minutes: int = Field(..., ge=1)
    margin_minutes: int = Field(..., ge=0)
    # Minimum time between the end of a team's match and its next match
    min_rest_minutes: int = Field(default=0, ge=0, le=600)
    # Time between the last match of a stage and the first match of the next stage of a class
    stage_buffer_minutes: int = Field(default=10, ge=0, le=600)


class TournamentChangeStatusBody(BaseModelORM):
    status: TournamentStatus


class TournamentBody(TournamentUpdateBody):
    club_id: ClubId
