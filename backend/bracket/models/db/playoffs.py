from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import StageId

Name = Annotated[str, StringConstraints(min_length=1, max_length=50, strip_whitespace=True)]


class PlayoffBody(BaseModelORM):
    """
    One knockout bracket, e.g. "A playoff" for placings [1, 2] of every group. It can also take
    the best teams at one placing across all groups: `best_of_placing=3, best_ranks=[1, 2]` adds
    the two best third placed teams.
    """

    name: Name
    placings: list[Annotated[int, Field(ge=1)]] = []
    third_place_match: bool = False
    best_of_placing: int | None = Field(None, ge=1)
    best_ranks: list[Annotated[int, Field(ge=1)]] = []

    @model_validator(mode="after")
    def check_teams(self) -> Self:
        if len(self.placings) + len(self.best_ranks) < 1:
            raise ValueError(f"{self.name}: choose which teams play in this playoff")
        if (self.best_of_placing is None) != (len(self.best_ranks) < 1):
            raise ValueError(f"{self.name}: choose both the placing and which of the best teams")
        if self.best_of_placing in self.placings:
            raise ValueError(f"{self.name}: placing {self.best_of_placing} is already included")
        return self


class PlayoffsCreateBody(BaseModelORM):
    """
    Creates a new stage after `group_stage_id` with a knockout bracket per playoff.
    """

    group_stage_id: StageId
    stage_name: Name = "Playoffs"
    playoffs: list[PlayoffBody] = Field(min_length=1)

    @model_validator(mode="after")
    def check_placings(self) -> Self:
        all_placings = [placing for playoff in self.playoffs for placing in playoff.placings]
        if len(all_placings) != len(set(all_placings)):
            raise ValueError("Each placing can only go to one playoff")

        best = [
            (playoff.best_of_placing, rank)
            for playoff in self.playoffs
            for rank in playoff.best_ranks
        ]
        if len(best) != len(set(best)):
            raise ValueError("Each of the best teams can only go to one playoff")
        if any(placing in all_placings for placing, _ in best):
            raise ValueError("A placing can't go to a playoff both completely and partly")
        return self
