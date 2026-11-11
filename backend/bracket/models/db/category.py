from typing import Annotated

from heliclockter import datetime_utc
from pydantic import Field, StringConstraints

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import CategoryId, TournamentId

# NFF: from the 13-year class, results and tables may be published (youth football).
# In children's football (12 and younger) they must not be.
YOUTH_FOOTBALL_MIN_AGE = 13


def default_results_public(age: int | None) -> bool:
    return age is None or age >= YOUTH_FOOTBALL_MIN_AGE


class CategoryInsertable(BaseModelORM):
    tournament_id: TournamentId
    name: str
    created: datetime_utc
    age: int | None = None
    results_public: bool = True


class Category(CategoryInsertable):
    id: CategoryId


class CategoryBody(BaseModelORM):
    """
    An age class (e.g. "G10" or "J12") within a tournament.

    `results_public` defaults to `False` for children's classes (age 12 and younger) and `True`
    otherwise, following the NFF rules.
    """

    name: Annotated[str, StringConstraints(min_length=1, max_length=50, strip_whitespace=True)]
    age: int | None = Field(None, ge=4, le=99)
    results_public: bool | None = None

    def get_results_public(self) -> bool:
        if self.results_public is not None:
            return self.results_public
        return default_results_public(self.age)
