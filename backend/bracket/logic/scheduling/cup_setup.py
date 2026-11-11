"""
Cup setup wizard: creates the whole structure of a cup in one go.

Per class: the class itself, a group stage with round robin groups (teams are drawn into the
groups later) and, optionally, a stage with A/B/C playoffs. Plus courts and playing hours for
the whole cup. The classes are described the same way as in the capacity calculator, so what
was calculated is what gets created.
"""

from typing import Annotated, Self

from fastapi import HTTPException
from pydantic import BaseModel, Field, StringConstraints, model_validator
from starlette import status

from bracket.database import database
from bracket.logic.planning.capacity import CapacityClass
from bracket.logic.scheduling.builder import build_matches_for_stage_item
from bracket.logic.scheduling.create_playoffs import create_playoffs
from bracket.logic.scheduling.cup_structure import PLAYOFF_NAMES, split_into_groups
from bracket.logic.scheduling.elimination import MIN_TEAMS_THIRD_PLACE_MATCH
from bracket.logic.subscriptions import check_requirement
from bracket.models.db.category import CategoryBody, default_results_public
from bracket.models.db.court import CourtsMultiBody
from bracket.models.db.playoffs import PlayoffBody, PlayoffsCreateBody
from bracket.models.db.stage_item import StageItemCreateBody, StageType
from bracket.models.db.time_window import TimeWindowsBody
from bracket.models.db.user import UserPublic
from bracket.sql.categories import get_all_categories_in_tournament, sql_create_category
from bracket.sql.courts import get_all_courts_in_tournament, sql_create_courts
from bracket.sql.stage_items import sql_create_stage_item_with_empty_inputs
from bracket.sql.stages import get_full_tournament_details, sql_create_stage
from bracket.sql.time_windows import sql_replace_time_windows
from bracket.utils.id_types import TournamentId

Name = Annotated[str, StringConstraints(min_length=1, max_length=40, strip_whitespace=True)]


class CupSetupClass(CapacityClass):
    # `None`: hidden for children's football (12 and younger), public otherwise (NFF)
    results_public: bool | None = None

    def get_results_public(self) -> bool:
        if self.results_public is not None:
            return self.results_public
        return default_results_public(self.age)

    @model_validator(mode="after")
    def check_hidden_results(self) -> Self:
        if not self.get_results_public() and self.has_playoffs:
            raise ValueError(
                f"{self.name}: playoffs are placed by results, so they aren't possible "
                "when the results of the class are hidden"
            )
        return self


class CupSetupNames(BaseModel):
    """Names of the created stages and stage items, in the language of the organiser."""

    group_stage: Name = "Group stage"
    group: Name = "Group"
    playoff_stage: Name = "Playoffs"
    # "{}" is replaced by the letter of the playoff: "A playoff", "B playoff", ...
    playoff: Name = "{} playoff"


class CupSetupBody(TimeWindowsBody):
    """
    The whole cup. Courts are added to existing ones; the time windows replace the existing
    ones (unless empty). Only possible while the tournament has no classes and no stages.
    """

    classes: list[CupSetupClass] = Field(min_length=1, max_length=40)
    courts: list[CourtsMultiBody] = Field(default=[], max_length=10)
    names: CupSetupNames = CupSetupNames()

    @model_validator(mode="after")
    def check_unique_names(self) -> Self:
        names = [cup_class.name.strip() for cup_class in self.classes]
        if len(names) != len(set(names)):
            raise ValueError("Each class needs its own name")
        return self


def group_letter(index: int) -> str:
    """A, B, ..., Z, AA, AB, ... like spreadsheet columns."""
    letters = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


async def check_cup_setup_allowed(
    tournament_id: TournamentId, body: CupSetupBody, user: UserPublic
) -> None:
    stages = await get_full_tournament_details(tournament_id)
    categories = await get_all_categories_in_tournament(tournament_id)
    if len(stages) > 0 or len(categories) > 0:
        raise bad_request("The setup wizard only works for a tournament without classes and stages")

    group_counts = [len(split_into_groups(c.team_count, c.group_size)) for c in body.classes]
    playoff_counts = [
        len(c.get_playoffs(split_into_groups(c.team_count, c.group_size))) for c in body.classes
    ]
    check_requirement(categories, user, "max_categories", additions=len(body.classes))
    stage_count = len(body.classes) + sum(1 for count in playoff_counts if count > 0)
    check_requirement(stages, user, "max_stages", additions=stage_count)
    check_requirement([], user, "max_stage_items", additions=sum(group_counts + playoff_counts))
    courts = await get_all_courts_in_tournament(tournament_id)
    check_requirement(courts, user, "max_courts", additions=sum(c.count for c in body.courts))


async def create_class(
    tournament_id: TournamentId, cup_class: CupSetupClass, names: CupSetupNames, user: UserPublic
) -> None:
    category = await sql_create_category(
        tournament_id,
        CategoryBody(
            name=cup_class.name,
            age=cup_class.age,
            results_public=cup_class.get_results_public(),
            duration_minutes=cup_class.duration_minutes,
            margin_minutes=cup_class.margin_minutes,
            min_rest_minutes=cup_class.min_rest_minutes,
            game_format=cup_class.game_format,
        ),
    )
    group_stage = await sql_create_stage(tournament_id, category.id, names.group_stage)
    group_sizes = split_into_groups(cup_class.team_count, cup_class.group_size)
    for index, size in enumerate(group_sizes):
        group = await sql_create_stage_item_with_empty_inputs(
            tournament_id,
            StageItemCreateBody(
                stage_id=group_stage.id,
                name=f"{names.group} {group_letter(index)}",
                type=StageType.ROUND_ROBIN,
                team_count=size,
            ),
        )
        await build_matches_for_stage_item(group, tournament_id)

    playoffs = cup_class.get_playoffs(group_sizes)
    if len(playoffs) > 0:
        await create_playoffs(
            tournament_id,
            PlayoffsCreateBody(
                group_stage_id=group_stage.id,
                stage_name=names.playoff_stage,
                playoffs=[
                    PlayoffBody(
                        name=names.playoff.replace("{}", PLAYOFF_NAMES[index]),
                        placings=placings,
                        best_of_placing=None,
                        third_place_match=cup_class.third_place_match
                        and len(group_sizes) * len(placings) >= MIN_TEAMS_THIRD_PLACE_MATCH,
                    )
                    for index, placings in enumerate(playoffs)
                ],
            ),
            user,
        )


async def set_up_cup(tournament_id: TournamentId, body: CupSetupBody, user: UserPublic) -> None:
    await check_cup_setup_allowed(tournament_id, body, user)
    async with database.transaction():
        for cup_class in body.classes:
            await create_class(tournament_id, cup_class, body.names, user)
        for courts in body.courts:
            await sql_create_courts(tournament_id, courts)
        if len(body.time_windows) > 0:
            await sql_replace_time_windows(tournament_id, body.time_windows)
