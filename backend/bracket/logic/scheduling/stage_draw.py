"""
The group draw of a stage: validates the request, runs the pure draw (`group_draw`) and saves
the teams in the empty slots of the groups.
"""

import random
from typing import Self

from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from starlette import status

from bracket.database import database
from bracket.logic.participating_clubs import get_club_names
from bracket.logic.scheduling.group_draw import (
    DrawGroup,
    DrawTeam,
    club_name_of,
    club_of,
    draw_groups,
)
from bracket.models.db.stage_item import StageType
from bracket.models.db.stage_item_inputs import StageItemInputEmpty, StageItemInputFinal
from bracket.models.db.team import MAX_POTS
from bracket.models.db.util import StageWithStageItems
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.teams import get_teams_by_id
from bracket.utils.id_types import (
    ParticipatingClubId,
    StageId,
    StageItemId,
    StageItemInputId,
    TeamId,
    TournamentId,
)


class DrawBody(BaseModel):
    """
    `pots`: the teams to draw, pot by pot (best teams first). One pot is a plain random draw.
    `seed`: the same seed gives the same draw.
    """

    pots: list[list[TeamId]] = Field(min_length=1, max_length=MAX_POTS)
    seed: int | None = None

    @model_validator(mode="after")
    def check_teams(self) -> Self:
        team_ids = [team_id for pot in self.pots for team_id in pot]
        if len(team_ids) < 1:
            raise ValueError("Choose the teams to draw")
        if len(team_ids) != len(set(team_ids)):
            raise ValueError("A team can only be in one pot")
        return self


class DrawPlacement(BaseModel):
    team_id: TeamId
    stage_item_id: StageItemId
    stage_item_input_id: StageItemInputId


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def get_groups(
    stage: StageWithStageItems, club_names: dict[ParticipatingClubId, str]
) -> tuple[list[StageItemId], list[DrawGroup]]:
    """The groups of the stage with their empty slots and the clubs already in them."""
    if len(stage.stage_items) < 1:
        raise bad_request("The stage has no groups")
    if any(item.type not in {StageType.ROUND_ROBIN, StageType.SWISS} for item in stage.stage_items):
        raise bad_request("Teams can only be drawn into round robin or swiss groups")

    stage_items = sorted(stage.stage_items, key=lambda item: (item.name, item.id))
    groups = [
        DrawGroup(
            free_slots=[
                input_.id
                for input_ in sorted(item.inputs, key=lambda input_: input_.slot)
                if isinstance(input_, StageItemInputEmpty)
            ],
            clubs=[
                club_of(input_.team.name, club_name_of(input_.team.club_id, club_names))
                for input_ in item.inputs
                if isinstance(input_, StageItemInputFinal)
            ],
            pots=[],
        )
        for item in stage_items
    ]
    return [item.id for item in stage_items], groups


async def check_teams(
    tournament_id: TournamentId,
    stage: StageWithStageItems,
    body: DrawBody,
    club_names: dict[ParticipatingClubId, str],
) -> dict[TeamId, DrawTeam]:
    team_ids = {team_id for pot in body.pots for team_id in pot}
    teams = await get_teams_by_id(team_ids, tournament_id)
    if len(teams) != len(team_ids):
        raise bad_request("Some of the teams don't exist in this tournament")
    if any(team.category_id != stage.category_id for team in teams):
        raise bad_request("All teams must belong to the class of the stage")
    if any(not team.registration_status.participates for team in teams):
        raise bad_request("Teams on the waitlist or rejected teams can't be drawn")
    placed = {
        input_.team_id
        for item in stage.stage_items
        for input_ in item.inputs
        if isinstance(input_, StageItemInputFinal)
    }
    if team_ids & placed:
        raise bad_request("Some of the teams are already in a group of this stage")
    return {
        team.id: DrawTeam(team.id, club_of(team.name, club_name_of(team.club_id, club_names)))
        for team in teams
    }


async def draw_stage(
    tournament_id: TournamentId, stage_id: StageId, body: DrawBody
) -> list[DrawPlacement]:
    async with database.transaction():
        # One draw at a time per stage: a second one sees the result of the first
        await database.execute(
            "SELECT id FROM stages WHERE id = :stage_id FOR UPDATE", values={"stage_id": stage_id}
        )
        stages = await get_full_tournament_details(tournament_id)
        stage = next((stage for stage in stages if stage.id == stage_id), None)
        if stage is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the stage")

        club_names = await get_club_names(tournament_id)
        teams = await check_teams(tournament_id, stage, body, club_names)
        stage_item_ids, groups = get_groups(stage, club_names)
        try:
            placements = draw_groups(
                [[teams[team_id] for team_id in pot] for pot in body.pots],
                groups,
                random.Random(body.seed),
            )
        except ValueError as error:
            raise bad_request(str(error)) from error

        for placement in placements:
            await database.execute(
                """
                UPDATE stage_item_inputs
                SET team_id = :team_id
                WHERE id = :input_id AND tournament_id = :tournament_id AND team_id IS NULL
                """,
                values={
                    "team_id": placement.team_id,
                    "input_id": placement.slot_id,
                    "tournament_id": tournament_id,
                },
            )

    return [
        DrawPlacement(
            team_id=TeamId(placement.team_id),
            stage_item_id=stage_item_ids[placement.group_index],
            stage_item_input_id=StageItemInputId(placement.slot_id),
        )
        for placement in placements
    ]
