"""
The format of a class: its groups and the playoffs after them, changed in one go.

- Groups: before the draw, the groups are made again for the registered teams in groups of about
  `group_size` (the same way as the setup wizard). After the draw the groups stay as they are, so
  only a change that keeps their sizes is possible.
- Playoffs: made again with the same placings, or from a preset (none, A, A+B, A+B+C), as long as
  they haven't started.

Only for a class whose stages are the group stage plus at most one playoff stage fed by it;
anything else is changed by hand on the stages page.
"""

from typing import Annotated

from fastapi import HTTPException
from pydantic import BaseModel, Field, StringConstraints
from starlette import status

from bracket.database import database
from bracket.logic.planning.matches import update_start_times_of_matches
from bracket.logic.results_visibility import check_advancing_allowed
from bracket.logic.scheduling.builder import build_matches_for_stage_item
from bracket.logic.scheduling.create_playoffs import create_playoffs
from bracket.logic.scheduling.cup_setup import group_letter
from bracket.logic.scheduling.cup_structure import (
    MAX_TEAMS_PER_PLAYOFF,
    PLAYOFF_NAMES,
    PlayoffPreset,
    split_into_groups,
    split_placings,
)
from bracket.logic.scheduling.elimination import MIN_TEAMS_THIRD_PLACE_MATCH
from bracket.logic.subscriptions import check_requirement
from bracket.models.db.playoffs import PlayoffBody, PlayoffsCreateBody
from bracket.models.db.stage_item import StageItemCreateBody, StageType
from bracket.models.db.stage_item_inputs import (
    StageItemInputBestOf,
    StageItemInputEmpty,
    StageItemInputFinal,
    StageItemInputTentative,
)
from bracket.models.db.user import UserPublic
from bracket.models.db.util import StageItemWithRounds, StageWithStageItems
from bracket.sql.categories import get_category_by_id
from bracket.sql.shared import sql_delete_stage_item_with_foreign_keys
from bracket.sql.stage_items import sql_create_stage_item_with_empty_inputs
from bracket.sql.stages import get_full_tournament_details, sql_delete_stage
from bracket.sql.teams import get_teams_with_members
from bracket.utils.id_types import StageId, TournamentId

MAX_GROUP_SIZE = 10  # Also in the error message below

Name = Annotated[str, StringConstraints(min_length=1, max_length=40, strip_whitespace=True)]


class FormatChange(BaseModel):
    """
    `playoffs`: empty keeps the playoffs with their placings, a preset makes them again.
    `third_place_match`: empty keeps it as it is per playoff. The names are used for a playoff
    stage or playoff that doesn't exist yet ("{}" is the letter of the playoff).
    """

    group_size: int
    playoffs: PlayoffPreset | None = None
    third_place_match: bool | None = None
    playoff_stage_name: Name = "Playoffs"
    playoff_name: Name = Field(default="{} playoff", pattern=r"\{\}")


class FittedPlayoff(BaseModel):
    name: str
    team_count: int


class FitGroupsPreview(BaseModel):
    """What fitting the groups would create, for the confirmation."""

    team_count: int
    current_group_sizes: list[int]
    group_sizes: list[int]
    matches_per_team_min: int
    matches_per_team_max: int
    match_count: int
    playoffs: list[FittedPlayoff]
    # Playoffs of today that are left out (too few teams, or fewer playoffs chosen)
    removed_playoffs: list[str]
    # False after the draw: the groups and their teams stay, only the playoffs change
    groups_rebuilt: bool
    # Matches that are made again but already had a time: the class has to be planned again
    planned_match_count: int


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def playoff_body(item: StageItemWithRounds, group_ids: set[int]) -> PlayoffBody:
    """The playoff settings that created a knockout stage item fed by the groups."""
    placings: set[int] = set()
    best_of_placing: int | None = None
    best_ranks: list[int] = []
    for input_ in item.inputs:
        if isinstance(input_, StageItemInputTentative) and (
            input_.winner_from_stage_item_id in group_ids
        ):
            placings.add(input_.winner_position)
        elif isinstance(input_, StageItemInputBestOf):
            best_of_placing = input_.winner_position
            best_ranks.append(input_.best_rank)
        else:
            raise bad_request(
                "A playoff isn't filled from the groups only: change the groups on the stages page"
            )
    last_round = max(item.rounds, key=lambda round_: round_.id, default=None)
    return PlayoffBody(
        name=item.name,
        placings=sorted(placings),
        best_of_placing=best_of_placing,
        best_ranks=sorted(best_ranks),
        # The last round holds the final and, if there is one, the match for third place
        third_place_match=last_round is not None and len(last_round.matches) > 1,
    )


def fit_playoff(playoff: PlayoffBody, group_sizes: list[int]) -> PlayoffBody | None:
    """The playoff for the new groups: placings the smallest group doesn't have are left out."""
    smallest_group = min(group_sizes)
    placings = [placing for placing in playoff.placings if placing <= smallest_group]
    best_of_placing = playoff.best_of_placing
    best_ranks: list[int] = []
    if best_of_placing is not None and best_of_placing not in placings:
        candidates = sum(1 for size in group_sizes if size >= best_of_placing)
        best_ranks = [rank for rank in playoff.best_ranks if rank <= candidates]
    team_count = len(group_sizes) * len(placings) + len(best_ranks)
    if not 2 <= team_count <= MAX_TEAMS_PER_PLAYOFF:
        return None
    return PlayoffBody(
        name=playoff.name,
        placings=placings,
        best_of_placing=best_of_placing if len(best_ranks) > 0 else None,
        best_ranks=best_ranks,
        third_place_match=playoff.third_place_match and team_count >= MIN_TEAMS_THIRD_PLACE_MATCH,
    )


def knockout_match_count(team_count: int, third_place_match: bool) -> int:
    return team_count - 1 + (1 if third_place_match else 0)


class FitPlan(BaseModel):
    group_stage: StageWithStageItems
    playoff_stage: StageWithStageItems | None
    group_sizes: list[int]
    playoffs: list[PlayoffBody]
    groups_rebuilt: bool
    playoff_stage_name: str
    preview: FitGroupsPreview


def preset_playoffs(
    change: FormatChange, group_sizes: list[int], old_playoffs: list[PlayoffBody]
) -> list[PlayoffBody]:
    """Playoffs for a preset: the placings split evenly, with the names of today's playoffs."""
    assert change.playoffs is not None
    placings = split_placings(min(group_sizes), change.playoffs.playoff_count)
    return [
        PlayoffBody(
            name=old_playoffs[index].name
            if index < len(old_playoffs)
            else change.playoff_name.replace("{}", PLAYOFF_NAMES[index]),
            placings=playoff_placings,
            best_of_placing=None,
            third_place_match=change.third_place_match is True
            or (
                change.third_place_match is None
                and index < len(old_playoffs)
                and old_playoffs[index].third_place_match
            ),
        )
        for index, playoff_placings in enumerate(placings)
    ]


def playoff_team_count(playoff: PlayoffBody, group_count: int) -> int:
    return group_count * len(playoff.placings) + len(playoff.best_ranks)


async def plan_fit(tournament_id: TournamentId, stage_id: StageId, change: FormatChange) -> FitPlan:
    if not 2 <= change.group_size <= MAX_GROUP_SIZE:
        raise bad_request("A group has between 2 and 10 teams")
    stages = await get_full_tournament_details(tournament_id)
    group_stage = next((stage for stage in stages if stage.id == stage_id), None)
    if group_stage is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the stage")
    if group_stage.category_id is None:
        raise bad_request("Only the groups of a class can be fitted to its teams")
    groups = sorted(group_stage.stage_items, key=lambda item: (item.name, item.id))
    if len(groups) < 1 or any(item.type is not StageType.ROUND_ROBIN for item in groups):
        raise bad_request("Only a stage with round robin groups can be fitted")
    drawn = any(
        not isinstance(input_, StageItemInputEmpty) for item in groups for input_ in item.inputs
    )

    other_stages = [
        stage
        for stage in stages
        if stage.category_id == group_stage.category_id and stage.id != group_stage.id
    ]
    group_ids: set[int] = {item.id for item in groups}
    if len(other_stages) > 1 or any(
        item.type is not StageType.SINGLE_ELIMINATION
        for stage in other_stages
        for item in stage.stage_items
    ):
        raise bad_request(
            "The class has more stages than groups and playoffs: change them on the stages page"
        )
    playoff_stage = other_stages[0] if len(other_stages) > 0 else None
    if playoff_stage is not None and (
        playoff_stage.is_active
        or any(
            isinstance(input_, StageItemInputFinal)
            for item in playoff_stage.stage_items
            for input_ in item.inputs
        )
    ):
        raise bad_request("The playoffs have started, so the format can't be changed any more")
    old_playoffs = (
        [
            playoff_body(item, group_ids)
            for item in sorted(playoff_stage.stage_items, key=lambda item: item.id)
        ]
        if playoff_stage is not None
        else []
    )

    teams = await get_teams_with_members(tournament_id, category_id=group_stage.category_id)
    team_count = len([team for team in teams if not team.withdrawn])
    if team_count < 2:
        raise bad_request("The class needs at least 2 teams")
    current_sizes = [item.team_count for item in groups]
    group_sizes = split_into_groups(team_count, change.group_size)
    if drawn and sorted(group_sizes) != sorted(current_sizes):
        raise bad_request("The groups already have teams: fit them before the draw")
    if drawn:
        # The groups stay with their teams: the playoffs are made for these groups
        group_sizes = current_sizes

    if change.playoffs is not None:
        new_playoffs = preset_playoffs(change, group_sizes, old_playoffs)
    else:
        new_playoffs = [
            playoff.model_copy(
                update={"third_place_match": change.third_place_match}
                if change.third_place_match is not None
                else {}
            )
            for playoff in old_playoffs
        ]
    fitted = [fit_playoff(playoff, group_sizes) for playoff in new_playoffs]
    playoffs = [playoff for playoff in fitted if playoff is not None]
    if len(playoffs) > 0:
        check_advancing_allowed(await get_category_by_id(tournament_id, group_stage.category_id))
    kept_names = {playoff.name for playoff in playoffs}

    # Stages that are made again lose their planned times
    class_stages = [group_stage, *other_stages] if not drawn else other_stages
    preview = FitGroupsPreview(
        team_count=team_count,
        current_group_sizes=current_sizes,
        group_sizes=group_sizes,
        matches_per_team_min=min(group_sizes) - 1,
        matches_per_team_max=max(group_sizes) - 1,
        match_count=sum(size * (size - 1) // 2 for size in group_sizes)
        + sum(
            knockout_match_count(
                playoff_team_count(playoff, len(group_sizes)), playoff.third_place_match
            )
            for playoff in playoffs
        ),
        playoffs=[
            FittedPlayoff(
                name=playoff.name,
                team_count=playoff_team_count(playoff, len(group_sizes)),
            )
            for playoff in playoffs
        ],
        removed_playoffs=[old.name for old in old_playoffs if old.name not in kept_names],
        groups_rebuilt=not drawn,
        planned_match_count=sum(
            1
            for stage in class_stages
            for item in stage.stage_items
            for round_ in item.rounds
            for match in round_.matches
            if match.start_time is not None
        ),
    )
    return FitPlan(
        group_stage=group_stage,
        playoff_stage=playoff_stage,
        group_sizes=group_sizes,
        playoffs=playoffs,
        groups_rebuilt=not drawn,
        playoff_stage_name=playoff_stage.name
        if playoff_stage is not None
        else change.playoff_stage_name,
        preview=preview,
    )


def group_name_prefix(group_stage: StageWithStageItems) -> str:
    """The name of the groups without their letter: "Pulje" for "Pulje A"; "Group" otherwise."""
    names = sorted(item.name for item in group_stage.stage_items)
    prefix, _, letter = names[0].rpartition(" ") if names else ("", "", "")
    return prefix if prefix and letter.isalpha() and letter.isupper() else "Group"


async def rebuild_groups(tournament_id: TournamentId, plan: FitPlan) -> None:
    prefix = group_name_prefix(plan.group_stage)
    ranking_id = plan.group_stage.stage_items[0].ranking_id
    for item in plan.group_stage.stage_items:
        await sql_delete_stage_item_with_foreign_keys(item.id)
    for index, size in enumerate(plan.group_sizes):
        group = await sql_create_stage_item_with_empty_inputs(
            tournament_id,
            StageItemCreateBody(
                stage_id=plan.group_stage.id,
                name=f"{prefix} {group_letter(index)}",
                type=StageType.ROUND_ROBIN,
                team_count=size,
                ranking_id=ranking_id,
            ),
        )
        await build_matches_for_stage_item(group, tournament_id)


async def fit_groups(
    tournament_id: TournamentId, stage_id: StageId, change: FormatChange, user: UserPublic
) -> FitGroupsPreview:
    async with database.transaction():
        # One change at a time per stage (and no draw in between)
        await database.execute(
            "SELECT id FROM stages WHERE id = :stage_id FOR UPDATE", values={"stage_id": stage_id}
        )
        plan = await plan_fit(tournament_id, stage_id, change)
        replaced_stages = {plan.group_stage.id} if plan.groups_rebuilt else set()
        if plan.playoff_stage is not None:
            replaced_stages.add(plan.playoff_stage.id)
        kept_items = [
            item
            for stage in await get_full_tournament_details(tournament_id)
            if stage.id not in replaced_stages
            for item in stage.stage_items
        ]
        check_requirement(
            kept_items,
            user,
            "max_stage_items",
            additions=(len(plan.group_sizes) if plan.groups_rebuilt else 0) + len(plan.playoffs),
        )

        # Playoffs first: their inputs point at the groups
        if plan.playoff_stage is not None:
            for item in plan.playoff_stage.stage_items:
                await sql_delete_stage_item_with_foreign_keys(item.id)
            await sql_delete_stage(tournament_id, plan.playoff_stage.id)

        if plan.groups_rebuilt:
            await rebuild_groups(tournament_id, plan)

        if len(plan.playoffs) > 0:
            await create_playoffs(
                tournament_id,
                PlayoffsCreateBody(
                    group_stage_id=plan.group_stage.id,
                    stage_name=plan.playoff_stage_name,
                    playoffs=plan.playoffs,
                ),
                user,
            )
        await update_start_times_of_matches(tournament_id)
    return plan.preview
