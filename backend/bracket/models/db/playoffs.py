from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import StageId

Name = Annotated[str, StringConstraints(min_length=1, max_length=50, strip_whitespace=True)]


class PlayoffBody(BaseModelORM):
    """
    One knockout bracket, e.g. "A playoff" for placings [1, 2] of every group.
    """

    name: Name
    placings: list[Annotated[int, Field(ge=1)]] = Field(min_length=1)
    third_place_match: bool = False


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
        return self
