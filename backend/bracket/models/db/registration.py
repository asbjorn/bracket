from typing import Annotated, Literal, Self

from heliclockter import datetime_utc
from pydantic import BaseModel, EmailStr, Field, StringConstraints, model_validator

from bracket.models.db.team import MAX_SQUAD_SIZE, ClubName, RegistrationStatus, TeamName
from bracket.utils.id_types import CategoryId, TeamId
from bracket.utils.text import SingleLine

MAX_TEAMS_PER_CLASS = 256
MAX_ENTRY_FEE = 100_000

PersonName = Annotated[
    str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True), SingleLine
]
# Digits and spaces, optionally a leading +, e.g. "+47 912 34 567"
Phone = Annotated[
    str, StringConstraints(pattern=r"^\+?[0-9 ]{5,20}$", strip_whitespace=True, max_length=21)
]
Comment = Annotated[str, StringConstraints(max_length=500, strip_whitespace=True)]


class RegistrationSettingsBody(BaseModel):
    """Public sign-up for one class. Beyond `max_teams` teams, new teams go to the waitlist."""

    registration_open: bool
    registration_deadline: datetime_utc | None = None
    max_teams: int | None = Field(default=None, ge=1, le=MAX_TEAMS_PER_CLASS)
    entry_fee: int | None = Field(default=None, ge=0, le=MAX_ENTRY_FEE)


class EntryFeeBody(BaseModel):
    """Sets the entry fee (NOK per team) of several classes at once."""

    category_ids: list[CategoryId] = Field(min_length=1, max_length=100)
    entry_fee: int | None = Field(default=None, ge=0, le=MAX_ENTRY_FEE)


class PublicRegistrationClass(BaseModel):
    """A class open for sign-up, as shown on the public form (no personal data)."""

    id: CategoryId
    name: str
    age: int | None
    registration_deadline: datetime_utc | None
    entry_fee: int | None
    # `None`: no limit; 0: new teams go to the waitlist
    spots_left: int | None


MAX_TEAMS_PER_SIGN_UP = 10


class RegistrationTeam(BaseModel):
    category_id: CategoryId
    team_name: TeamName
    squad_size: int | None = Field(default=None, ge=1, le=MAX_SQUAD_SIZE)


class PublicRegistrationBody(BaseModel):
    """
    A sign-up: one team (`category_id`, `team_name`), or several teams of one club in one go
    (`teams`, possibly in different classes) with the same contact person.
    """

    category_id: CategoryId | None = None
    team_name: TeamName | None = None
    teams: list[RegistrationTeam] = Field(default=[], max_length=MAX_TEAMS_PER_SIGN_UP)
    club_name: ClubName | None = None
    contact_name: PersonName
    contact_email: Annotated[EmailStr, Field(max_length=254)]
    contact_phone: Phone
    comment: Comment | None = None
    # The contact details may be stored and used by the organiser for this cup
    consent: Literal[True]
    # Honeypot: hidden in the form, so only bots fill it in
    website: Annotated[str, Field(max_length=200)] = ""

    @model_validator(mode="after")
    def check_teams(self) -> Self:
        if not self.teams:
            if self.category_id is None or self.team_name is None:
                raise ValueError("Choose a class and a team name")
            self.teams = [
                RegistrationTeam(
                    category_id=self.category_id, team_name=self.team_name, squad_size=None
                )
            ]
        names = [(team.category_id, team.team_name.casefold()) for team in self.teams]
        if len(names) != len(set(names)):
            raise ValueError("Two teams in the same class have the same name")
        return self


class TeamRegistrationResult(BaseModel):
    team_name: str
    category_id: CategoryId
    registration_status: RegistrationStatus
    waitlist_place: int | None


class PublicRegistrationResult(BaseModel):
    """The first team (for one-team sign-ups) and all teams of the sign-up."""

    team_name: str
    registration_status: RegistrationStatus
    waitlist_place: int | None
    teams: list[TeamRegistrationResult]


class Registration(BaseModel):
    """A team with its registration, for the organiser only: contains personal data."""

    team_id: TeamId
    team_name: str
    club_name: str | None
    category_id: CategoryId | None
    registration_status: RegistrationStatus
    withdrawn: bool
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    comment: str | None
    registered_at: datetime_utc | None
    paid: bool
    squad_reported: bool
    waitlist_place: int | None


class RegistrationUpdateBody(BaseModel):
    registration_status: RegistrationStatus
    paid: bool
    squad_reported: bool
    contact_name: PersonName | None = None
    contact_email: Annotated[EmailStr, Field(max_length=254)] | None = None
    contact_phone: Phone | None = None
    comment: Comment | None = None
