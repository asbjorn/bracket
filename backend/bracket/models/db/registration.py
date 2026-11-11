from typing import Annotated, Literal

from heliclockter import datetime_utc
from pydantic import BaseModel, EmailStr, Field, StringConstraints

from bracket.models.db.team import ClubName, RegistrationStatus
from bracket.utils.id_types import CategoryId, TeamId

MAX_TEAMS_PER_CLASS = 256
MAX_ENTRY_FEE = 100_000

TeamName = Annotated[str, StringConstraints(min_length=1, max_length=30, strip_whitespace=True)]
PersonName = Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]
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


class PublicRegistrationBody(BaseModel):
    category_id: CategoryId
    team_name: TeamName
    club_name: ClubName | None = None
    contact_name: PersonName
    contact_email: Annotated[EmailStr, Field(max_length=254)]
    contact_phone: Phone
    comment: Comment | None = None
    # The contact details may be stored and used by the organiser for this cup
    consent: Literal[True]
    # Honeypot: hidden in the form, so only bots fill it in
    website: Annotated[str, Field(max_length=200)] = ""


class PublicRegistrationResult(BaseModel):
    team_name: str
    registration_status: RegistrationStatus
    waitlist_place: int | None


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
