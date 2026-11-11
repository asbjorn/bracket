from typing import Annotated, Self

from heliclockter import datetime_utc, timedelta
from pydantic import BaseModel, Field, StringConstraints, ValidationError, model_validator

from bracket.models.db.discipline import MatchCard, SuspendedPlayer
from bracket.models.db.match import MatchBody, MatchResultType
from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import (
    CourtId,
    MatchDayNoticeId,
    MatchId,
    RoundId,
    ScoreLinkId,
    TeamId,
    TournamentId,
)

# Old links must stop working: at most this long ahead
MAX_VALID_DAYS = 60


def check_valid_until(valid_until: datetime_utc | None) -> None:
    if valid_until is None:
        return
    if valid_until <= datetime_utc.now():
        raise ValueError("A link must be valid until a moment in the future")
    if valid_until > datetime_utc.now() + timedelta(days=MAX_VALID_DAYS):
        raise ValueError(f"A link can be valid for at most {MAX_VALID_DAYS} days")


class ScoreLinkBody(BaseModelORM):
    name: Annotated[str, StringConstraints(min_length=1, max_length=50, strip_whitespace=True)]
    # Only results of matches on this court; None: the whole tournament
    court_id: CourtId | None = None
    # `None`: until the cup is over (the end of its last playing hours, plus a day)
    valid_until: datetime_utc | None = None

    @model_validator(mode="after")
    def check_validity(self) -> Self:
        check_valid_until(self.valid_until)
        return self


class ScoreLinkValidityBody(BaseModel):
    """Extends (or shortens) a link without changing it: the QR codes keep working."""

    valid_until: datetime_utc | None = None

    @model_validator(mode="after")
    def check_validity(self) -> Self:
        check_valid_until(self.valid_until)
        return self


class ScoreLink(BaseModelORM):
    id: ScoreLinkId
    tournament_id: TournamentId
    court_id: CourtId | None
    name: str
    created: datetime_utc
    expires_at: datetime_utc
    revoked_at: datetime_utc | None


class ScoreLinkCreated(BaseModel):
    link: ScoreLink
    # Shown only once: the database has only its hash
    token: str


class ScoreEntryMatch(BaseModel):
    """A match as the score keeper sees it."""

    id: MatchId
    round_id: RoundId
    court_id: CourtId | None
    court_name: str | None
    start_time: datetime_utc | None
    duration_minutes: int
    category_name: str | None
    stage_item_name: str
    team1_id: TeamId | None
    team1_name: str | None
    team2_id: TeamId | None
    team2_name: str | None
    team1_checked_in: bool
    team2_checked_in: bool
    score1: int
    score2: int
    penalties1: int | None
    penalties2: int | None
    played: bool
    started_at: datetime_utc | None = None
    result_type: MatchResultType
    # Names only, never contact details
    referee_name: str | None = None
    assistant_names: list[str] = []
    # Discipline (13+ with public results): cards of the match and who sits it out
    discipline_allowed: bool = False
    cards: list[MatchCard] = []
    suspended_players: list[SuspendedPlayer] = []


class ScoreEntryView(BaseModel):
    tournament_name: str
    link_name: str
    court_id: CourtId | None
    court_name: str | None
    expires_at: datetime_utc
    # The result of a walkover, e.g. 3 for 3-0
    walkover_goals: int
    matches: list[ScoreEntryMatch]


class ScoreEntryBody(BaseModel):
    score1: int = Field(ge=0, le=99)
    score2: int = Field(ge=0, le=99)
    result_type: MatchResultType = MatchResultType.NORMAL
    penalties1: int | None = Field(None, ge=0, le=99)
    penalties2: int | None = Field(None, ge=0, le=99)
    played: bool = True

    @model_validator(mode="after")
    def check_result(self) -> Self:
        # Same rules as when the organiser enters a result
        try:
            self.to_match_body(RoundId(0), None, None, None)
        except ValidationError as error:
            raise ValueError(error.errors()[0]["msg"].removeprefix("Value error, ")) from error
        return self

    def to_match_body(
        self,
        round_id: RoundId,
        court_id: CourtId | None,
        custom_duration_minutes: int | None,
        custom_margin_minutes: int | None,
    ) -> MatchBody:
        return MatchBody(
            round_id=round_id,
            court_id=court_id,
            custom_duration_minutes=custom_duration_minutes,
            custom_margin_minutes=custom_margin_minutes,
            stage_item_input1_score=self.score1,
            stage_item_input2_score=self.score2,
            result_type=self.result_type,
            stage_item_input1_penalties=self.penalties1,
            stage_item_input2_penalties=self.penalties2,
            played=self.played,
        )


class MatchDayNoticeBody(BaseModel):
    delay_minutes: int | None = Field(None, ge=1, le=240)
    message: Annotated[str, StringConstraints(max_length=300, strip_whitespace=True)] = ""

    @model_validator(mode="after")
    def check_content(self) -> Self:
        if self.delay_minutes is None and self.message == "":
            raise ValueError("Enter a delay or a message")
        return self


class MatchDayNotice(BaseModelORM):
    id: MatchDayNoticeId
    tournament_id: TournamentId
    court_id: CourtId | None
    score_link_id: ScoreLinkId | None
    delay_minutes: int | None
    message: str
    created: datetime_utc
    resolved: bool


class WalkoverBody(BaseModel):
    winner_team_id: TeamId


class CheckInBody(BaseModel):
    checked_in: bool


class MatchStartedBody(BaseModel):
    """A started match keeps its pitch and time when the schedule is changed."""

    started: bool
