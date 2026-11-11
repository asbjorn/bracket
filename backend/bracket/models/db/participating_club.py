from typing import Annotated, Self

from heliclockter import datetime_utc
from pydantic import BaseModel, Field, StringConstraints, model_validator

from bracket.models.db.shared import BaseModelORM
from bracket.models.db.team import ClubName
from bracket.utils.id_types import CategoryId, ParticipatingClubId, TeamId, TournamentId
from bracket.utils.text import SingleLine

MAX_NEW_TEAMS = 50
MAX_TEAMS_PER_CLUB = 200

TeamName = Annotated[
    str, StringConstraints(min_length=1, max_length=30, strip_whitespace=True), SingleLine
]


class ParticipatingClub(BaseModelORM):
    """A club taking part in a cup with one or more teams (not an organiser's club)."""

    id: ParticipatingClubId
    tournament_id: TournamentId
    name: str
    created: datetime_utc


class ClubTeam(BaseModel):
    id: TeamId
    name: str
    category_id: CategoryId | None


class ParticipatingClubWithTeams(ParticipatingClub):
    teams: list[ClubTeam]


class NewClubTeam(BaseModel):
    name: TeamName
    category_id: CategoryId | None = None


class ParticipatingClubCreateBody(BaseModelORM):
    """
    Creates a club with its teams at once: new teams, and/or existing teams without a club.
    """

    name: ClubName
    new_teams: list[NewClubTeam] = Field(default=[], max_length=MAX_NEW_TEAMS)
    team_ids: list[TeamId] = Field(default=[], max_length=MAX_TEAMS_PER_CLUB)

    @model_validator(mode="after")
    def check_unique(self) -> Self:
        if len(self.team_ids) != len(set(self.team_ids)):
            raise ValueError("A team can only be added once")
        names = [(team.name.lower(), team.category_id) for team in self.new_teams]
        if len(names) != len(set(names)):
            raise ValueError("Two new teams in the same class have the same name")
        return self


class ParticipatingClubUpdateBody(BaseModelORM):
    """Renames the club and sets exactly which teams belong to it."""

    name: ClubName
    team_ids: list[TeamId] = Field(default=[], max_length=MAX_TEAMS_PER_CLUB)

    @model_validator(mode="after")
    def check_unique(self) -> Self:
        if len(self.team_ids) != len(set(self.team_ids)):
            raise ValueError("A team can only be added once")
        return self
