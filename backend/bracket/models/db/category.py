from typing import Annotated

from heliclockter import datetime_utc
from pydantic import Field, StringConstraints

from bracket.models.db.game_format import GameFormat
from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import CategoryId, TournamentId
from bracket.utils.text import SingleLine

# NFF: from the 13-year class, results and tables may be published (youth football).
# In children's football (12 and younger) they must not be.
YOUTH_FOOTBALL_MIN_AGE = 13


MAX_MATCHES_PER_DAY_LIMIT = 20


def max_matches_per_day_for_age(age: int | None) -> int | None:
    """
    A sensible limit of matches per team per day when the class doesn't set its own: younger
    players play more but shorter matches. Many teams aged 10-13 manage 4-5 matches a day before
    concentration drops (AreaCopa); 11v11 youth teams rarely play more than 3.
    """
    if age is None:
        return None
    if age <= 9:
        return 6
    if age <= 13:
        return 5
    if age <= 16:
        return 4
    return 3


def default_results_public(age: int | None) -> bool:
    return age is None or age >= YOUTH_FOOTBALL_MIN_AGE


class CategoryInsertable(BaseModelORM):
    tournament_id: TournamentId
    name: str
    created: datetime_utc
    age: int | None = None
    results_public: bool = True
    # Overrides of the tournament defaults for matches of this class
    duration_minutes: int | None = None
    margin_minutes: int | None = None
    min_rest_minutes: int | None = None
    game_format: GameFormat | None = None
    # Public sign-up
    registration_open: bool = False
    registration_deadline: datetime_utc | None = None
    max_teams: int | None = None
    entry_fee: int | None = None
    # `None`: the default for the age
    max_matches_per_day: int | None = None

    def get_max_matches_per_day(self) -> int | None:
        if self.max_matches_per_day is not None:
            return self.max_matches_per_day
        return max_matches_per_day_for_age(self.age)


class Category(CategoryInsertable):
    id: CategoryId


class CategoryBody(BaseModelORM):
    """
    An age class (e.g. "G10" or "J12") within a tournament.

    `results_public` defaults to `False` for children's classes (age 12 and younger) and `True`
    otherwise, following the NFF rules.
    """

    name: Annotated[
        str, StringConstraints(min_length=1, max_length=50, strip_whitespace=True), SingleLine
    ]
    age: int | None = Field(None, ge=4, le=99)
    results_public: bool | None = None
    duration_minutes: int | None = Field(None, ge=1, le=240)
    margin_minutes: int | None = Field(None, ge=0, le=120)
    min_rest_minutes: int | None = Field(None, ge=0, le=600)
    game_format: GameFormat | None = None
    # At most this many matches per team per day; `None`: the default for the age
    max_matches_per_day: int | None = Field(None, ge=1, le=MAX_MATCHES_PER_DAY_LIMIT)

    def get_results_public(self) -> bool:
        if self.results_public is not None:
            return self.results_public
        return default_results_public(self.age)
