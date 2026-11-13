"""
Moving a team to another place in the groups of a stage (drag and drop after the draw): to an
empty place, or swapped with the team in that place. Matches refer to places, not teams, so they
follow the teams by themselves; that's why teams that have played can't be moved.
"""

from fastapi import HTTPException
from pydantic import BaseModel
from starlette import status

from bracket.database import database
from bracket.models.db.stage_item import StageType
from bracket.models.db.stage_item_inputs import StageItemInputEmpty, StageItemInputFinal
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.id_types import StageId, StageItemInputId, TeamId, TournamentId

GROUP_TYPES = {StageType.ROUND_ROBIN, StageType.SWISS}


class MoveTeamBody(BaseModel):
    team_id: TeamId
    # The place to move to: an empty one, or the place of the team to swap with
    target_input_id: StageItemInputId


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


async def set_team(input_id: int, team_id: int | None) -> None:
    await database.execute(
        "UPDATE stage_item_inputs SET team_id = :team_id WHERE id = :input_id",
        values={"team_id": team_id, "input_id": input_id},
    )


async def move_team(tournament_id: TournamentId, stage_id: StageId, body: MoveTeamBody) -> None:
    async with database.transaction():
        # One change at a time per stage (and no draw in between)
        await database.execute(
            "SELECT id FROM stages WHERE id = :stage_id FOR UPDATE", values={"stage_id": stage_id}
        )
        stages = await get_full_tournament_details(tournament_id)
        stage = next((stage for stage in stages if stage.id == stage_id), None)
        if stage is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the stage")
        if any(item.type not in GROUP_TYPES for item in stage.stage_items):
            raise bad_request("Teams can only be moved between groups")

        inputs = [input_ for item in stage.stage_items for input_ in item.inputs]
        source = next(
            (
                input_
                for input_ in inputs
                if isinstance(input_, StageItemInputFinal) and input_.team_id == body.team_id
            ),
            None,
        )
        if source is None:
            raise bad_request("The team isn't in a group of this stage")
        target = next((input_ for input_ in inputs if input_.id == body.target_input_id), None)
        if target is None or not isinstance(target, StageItemInputEmpty | StageItemInputFinal):
            raise bad_request("Could not find the place to move the team to")
        if source.id == target.id:
            return

        moved = {source.id, target.id}
        if any(
            match.played
            and (match.stage_item_input1_id in moved or match.stage_item_input2_id in moved)
            for item in stage.stage_items
            for round_ in item.rounds
            for match in round_.matches
        ):
            raise bad_request("Teams that have played a match in this stage can't be moved")

        other_team = target.team_id if isinstance(target, StageItemInputFinal) else None
        # Free the target first: a group can't have the same team twice, not even for a moment
        await set_team(target.id, None)
        await set_team(source.id, other_team)
        await set_team(target.id, body.team_id)
