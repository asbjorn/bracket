from fastapi import HTTPException
from starlette import status

from bracket.database import database
from bracket.logic.results_visibility import check_advancing_allowed
from bracket.logic.scheduling.builder import build_matches_for_stage_item
from bracket.logic.scheduling.elimination import MIN_TEAMS_THIRD_PLACE_MATCH
from bracket.logic.scheduling.playoffs import Qualifier, get_qualifiers_per_slot
from bracket.logic.subscriptions import check_requirement
from bracket.models.db.playoffs import PlayoffBody, PlayoffsCreateBody
from bracket.models.db.stage_item import StageItemWithInputsCreate, StageType
from bracket.models.db.stage_item_inputs import (
    StageItemInputCreateBody,
    StageItemInputCreateBodyTentative,
)
from bracket.models.db.user import UserPublic
from bracket.models.db.util import StageItemWithRounds, StageWithStageItems
from bracket.sql.categories import get_category_by_id
from bracket.sql.stage_items import sql_create_stage_item_with_inputs
from bracket.sql.stages import get_full_tournament_details, sql_create_stage
from bracket.utils.id_types import TournamentId

MAX_TEAMS_PER_PLAYOFF = 64


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def check_playoff(playoff: PlayoffBody, groups: list[StageItemWithRounds]) -> None:
    team_count = len(groups) * len(playoff.placings)
    if not 2 <= team_count <= MAX_TEAMS_PER_PLAYOFF:
        raise bad_request(f"{playoff.name}: a playoff needs between 2 and 64 teams")
    if playoff.third_place_match and team_count < MIN_TEAMS_THIRD_PLACE_MATCH:
        raise bad_request(f"{playoff.name}: a third place match needs at least 4 teams")
    for group in groups:
        if max(playoff.placings) > group.team_count:
            raise bad_request(
                f"{playoff.name}: {group.name} only has {group.team_count} teams, "
                f"so it has no number {max(playoff.placings)}"
            )


def get_playoff_inputs(
    playoff: PlayoffBody, groups: list[StageItemWithRounds]
) -> list[StageItemInputCreateBody]:
    qualifiers = [
        Qualifier(group_index, placing)
        for group_index in range(len(groups))
        for placing in playoff.placings
    ]
    return [
        StageItemInputCreateBodyTentative(
            slot=slot,
            winner_from_stage_item_id=groups[qualifier.group_index].id,
            winner_position=qualifier.placing,
        )
        for slot, qualifier in enumerate(get_qualifiers_per_slot(qualifiers), start=1)
    ]


async def create_playoffs(
    tournament_id: TournamentId, body: PlayoffsCreateBody, user: UserPublic
) -> None:
    stages = await get_full_tournament_details(tournament_id)
    group_stage: StageWithStageItems = next(s for s in stages if s.id == body.group_stage_id)
    groups = sorted(group_stage.stage_items, key=lambda group: group.name)

    if len(groups) < 1:
        raise bad_request("The group stage has no groups")
    if any(group.type not in {StageType.ROUND_ROBIN, StageType.SWISS} for group in groups):
        raise bad_request("Playoffs can only follow a stage with round robin or swiss groups")
    if group_stage.category_id is not None:
        check_advancing_allowed(await get_category_by_id(tournament_id, group_stage.category_id))
    for playoff in body.playoffs:
        check_playoff(playoff, groups)

    check_requirement(stages, user, "max_stages")
    existing_stage_items = [item for stage in stages for item in stage.stage_items]
    check_requirement(existing_stage_items, user, "max_stage_items", additions=len(body.playoffs))

    async with database.transaction():
        stage = await sql_create_stage(tournament_id, group_stage.category_id, body.stage_name)
        for playoff in body.playoffs:
            inputs = get_playoff_inputs(playoff, groups)
            stage_item = await sql_create_stage_item_with_inputs(
                tournament_id,
                StageItemWithInputsCreate(
                    stage_id=stage.id,
                    name=playoff.name,
                    type=StageType.SINGLE_ELIMINATION,
                    team_count=len(inputs),
                    third_place_match=playoff.third_place_match,
                    inputs=inputs,
                ),
            )
            await build_matches_for_stage_item(
                stage_item, tournament_id, third_place_match=playoff.third_place_match
            )
