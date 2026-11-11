"""
A level-split round ("nivådelt runde"): after the first groups, the organiser composes new
groups of teams of a similar level, by hand. Common in children's football, where results are
hidden: nothing is placed automatically from results, the organiser decides.
"""

from typing import Annotated, Self

from fastapi import HTTPException
from pydantic import BaseModel, Field, StringConstraints, model_validator
from starlette import status

from bracket.database import database
from bracket.logic.scheduling.builder import build_matches_for_stage_item
from bracket.logic.subscriptions import check_requirement
from bracket.models.db.stage_item import StageItemWithInputsCreate, StageType
from bracket.models.db.stage_item_inputs import StageItemInputCreateBodyFinal
from bracket.models.db.user import UserPublic
from bracket.sql.stage_items import sql_create_stage_item_with_inputs
from bracket.sql.stages import get_full_tournament_details, sql_create_stage
from bracket.sql.teams import get_teams_by_id
from bracket.utils.id_types import CategoryId, StageId, TeamId, TournamentId
from bracket.utils.text import SingleLine

Name = Annotated[
    str, StringConstraints(min_length=1, max_length=50, strip_whitespace=True), SingleLine
]
MAX_LEVEL_GROUPS = 16


class LevelGroup(BaseModel):
    name: Name
    team_ids: list[TeamId] = Field(min_length=2, max_length=10)


class LevelRoundBody(BaseModel):
    stage_name: Name
    groups: list[LevelGroup] = Field(min_length=1, max_length=MAX_LEVEL_GROUPS)

    @model_validator(mode="after")
    def check_teams_once(self) -> Self:
        team_ids = [team_id for group in self.groups for team_id in group.team_ids]
        if len(team_ids) != len(set(team_ids)):
            raise ValueError("A team can only be in one group")
        names = [group.name.casefold() for group in self.groups]
        if len(names) != len(set(names)):
            raise ValueError("Each group needs its own name")
        return self


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail)


async def create_level_round(
    tournament_id: TournamentId, category_id: CategoryId, body: LevelRoundBody, user: UserPublic
) -> StageId:
    team_ids = {team_id for group in body.groups for team_id in group.team_ids}
    teams = await get_teams_by_id(team_ids, tournament_id)
    if len(teams) != len(team_ids) or any(t.category_id != category_id for t in teams):
        raise bad_request("All teams must belong to this class")
    stages = await get_full_tournament_details(tournament_id)
    check_requirement(stages, user, "max_stages")
    items = [item for stage in stages for item in stage.stage_items]
    check_requirement(items, user, "max_stage_items", additions=len(body.groups))

    async with database.transaction():
        stage = await sql_create_stage(tournament_id, category_id, body.stage_name)
        for group in body.groups:
            stage_item = await sql_create_stage_item_with_inputs(
                tournament_id,
                StageItemWithInputsCreate(
                    stage_id=stage.id,
                    name=group.name,
                    type=StageType.ROUND_ROBIN,
                    team_count=len(group.team_ids),
                    inputs=[
                        StageItemInputCreateBodyFinal(slot=slot, team_id=team_id)
                        for slot, team_id in enumerate(group.team_ids, start=1)
                    ],
                ),
            )
            await build_matches_for_stage_item(stage_item, tournament_id)
    return stage.id
