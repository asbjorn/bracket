"""
Fit the groups of a class to its registered teams: before the draw, the groups of a group stage
are replaced by groups for the real number of teams, and the playoffs after it are created again
with the same placings (the same way as the setup wizard).

Only for a class whose groups have no teams yet and whose stages are the group stage plus at most
one playoff stage fed by it; anything else is changed by hand on the stages page.
"""

from fastapi import HTTPException
from pydantic import BaseModel
from starlette import status

from bracket.database import database
from bracket.logic.planning.matches import update_start_times_of_matches
from bracket.logic.scheduling.builder import build_matches_for_stage_item
from bracket.logic.scheduling.create_playoffs import create_playoffs
from bracket.logic.scheduling.cup_setup import group_letter
from bracket.logic.scheduling.cup_structure import MAX_TEAMS_PER_PLAYOFF, split_into_groups
from bracket.logic.scheduling.elimination import MIN_TEAMS_THIRD_PLACE_MATCH
from bracket.logic.subscriptions import check_requirement
from bracket.models.db.playoffs import PlayoffBody, PlayoffsCreateBody
from bracket.models.db.stage_item import StageItemCreateBody, StageType
from bracket.models.db.stage_item_inputs import (
    StageItemInputBestOf,
    StageItemInputEmpty,
    StageItemInputTentative,
)
from bracket.models.db.user import UserPublic
from bracket.models.db.util import StageItemWithRounds, StageWithStageItems
from bracket.sql.shared import sql_delete_stage_item_with_foreign_keys
from bracket.sql.stage_items import sql_create_stage_item_with_empty_inputs
from bracket.sql.stages import get_full_tournament_details, sql_delete_stage
from bracket.sql.teams import get_teams_with_members
from bracket.utils.id_types import StageId, TournamentId

MAX_GROUP_SIZE = 10  # Also in the error message below


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
    # Playoffs of today that get too few teams and are left out
    removed_playoffs: list[str]
    # Matches of the class that already have a time: the class has to be planned again
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
    preview: FitGroupsPreview


async def plan_fit(tournament_id: TournamentId, stage_id: StageId, group_size: int) -> FitPlan:
    if not 2 <= group_size <= MAX_GROUP_SIZE:
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
    if any(
        not isinstance(input_, StageItemInputEmpty) for item in groups for input_ in item.inputs
    ):
        raise bad_request("The groups already have teams: fit them before the draw")

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
    group_sizes = split_into_groups(team_count, group_size)
    fitted = [fit_playoff(playoff, group_sizes) for playoff in old_playoffs]
    playoffs = [playoff for playoff in fitted if playoff is not None]

    class_stages = [group_stage, *other_stages]
    preview = FitGroupsPreview(
        team_count=team_count,
        current_group_sizes=[item.team_count for item in groups],
        group_sizes=group_sizes,
        matches_per_team_min=min(group_sizes) - 1,
        matches_per_team_max=max(group_sizes) - 1,
        match_count=sum(size * (size - 1) // 2 for size in group_sizes)
        + sum(
            knockout_match_count(
                len(group_sizes) * len(playoff.placings) + len(playoff.best_ranks),
                playoff.third_place_match,
            )
            for playoff in playoffs
        ),
        playoffs=[
            FittedPlayoff(
                name=playoff.name,
                team_count=len(group_sizes) * len(playoff.placings) + len(playoff.best_ranks),
            )
            for playoff in playoffs
        ],
        removed_playoffs=[
            old.name for old, new in zip(old_playoffs, fitted, strict=True) if new is None
        ],
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
        preview=preview,
    )


def group_name_prefix(group_stage: StageWithStageItems) -> str:
    """The name of the groups without their letter: "Pulje" for "Pulje A"; "Group" otherwise."""
    names = sorted(item.name for item in group_stage.stage_items)
    prefix, _, letter = names[0].rpartition(" ") if names else ("", "", "")
    return prefix if prefix and letter.isalpha() and letter.isupper() else "Group"


async def fit_groups(
    tournament_id: TournamentId, stage_id: StageId, group_size: int, user: UserPublic
) -> FitGroupsPreview:
    async with database.transaction():
        # One change at a time per stage (and no draw in between)
        await database.execute(
            "SELECT id FROM stages WHERE id = :stage_id FOR UPDATE", values={"stage_id": stage_id}
        )
        plan = await plan_fit(tournament_id, stage_id, group_size)
        replaced_stages = {plan.group_stage.id}
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
            additions=len(plan.group_sizes) + len(plan.playoffs),
        )

        # Playoffs first: their inputs point at the groups
        if plan.playoff_stage is not None:
            for item in plan.playoff_stage.stage_items:
                await sql_delete_stage_item_with_foreign_keys(item.id)
            await sql_delete_stage(tournament_id, plan.playoff_stage.id)

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

        if len(plan.playoffs) > 0:
            assert plan.playoff_stage is not None
            await create_playoffs(
                tournament_id,
                PlayoffsCreateBody(
                    group_stage_id=plan.group_stage.id,
                    stage_name=plan.playoff_stage.name,
                    playoffs=plan.playoffs,
                ),
                user,
            )
        await update_start_times_of_matches(tournament_id)
    return plan.preview
