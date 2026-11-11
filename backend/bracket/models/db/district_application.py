from datetime import date
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from bracket.models.db.game_format import GameFormat

ShortText = Annotated[str, StringConstraints(max_length=200, strip_whitespace=True)]
LongText = Annotated[str, StringConstraints(max_length=4000, strip_whitespace=True)]


class TournamentDetails(BaseModel):
    """
    Cup facts the district (krets) asks for that Bracket doesn't know otherwise. Contact details
    are personal data and only shown to the organiser.
    """

    organiser_club: ShortText | None = None
    contact_name: ShortText | None = None
    contact_phone: ShortText | None = None
    contact_email: ShortText | None = None
    jury_chair_name: ShortText | None = None
    jury_chair_phone: ShortText | None = None
    venue: ShortText | None = None
    rules_summary: LongText | None = None
    notes: LongText | None = None


class PlayingDay(BaseModel):
    """A day of the cup in Norwegian time, with its playing hours, e.g. ["09:00-12:00"]."""

    day: date
    first_start: str
    last_end: str
    windows: list[str]


class CourtCount(BaseModel):
    game_format: GameFormat | None
    count: int


class ApplicationClass(BaseModel):
    name: str
    age: int | None
    game_format: GameFormat | None
    duration_minutes: int
    margin_minutes: int
    team_count: int
    max_teams: int | None
    entry_fee: int | None
    results_public: bool
    has_playoffs: bool
    match_count: int


class DistrictApplication(BaseModel):
    tournament_name: str
    details: TournamentDetails
    days: list[PlayingDay]
    courts: list[CourtCount]
    classes: list[ApplicationClass]
    team_count: int
    match_count: int
    rules_text: str | None
