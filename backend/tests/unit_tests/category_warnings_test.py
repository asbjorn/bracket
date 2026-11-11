from collections.abc import Callable
from itertools import combinations, count

from heliclockter import datetime_utc

from bracket.logic.category_warnings import (
    CategoryWarning,
    CategoryWarningCode,
    get_category_warnings,
    get_guaranteed_matches_per_stage_item,
)
from bracket.models.db.category import Category
from bracket.models.db.match import MatchWithDetails, MatchWithDetailsDefinitive
from bracket.models.db.stage_item import StageType
from bracket.models.db.stage_item_inputs import (
    StageItemInput,
    StageItemInputFinal,
    StageItemInputTentative,
)
from bracket.models.db.team import FullTeamWithPlayers, Team
from bracket.models.db.util import RoundWithMatches, StageItemWithRounds, StageWithStageItems
from bracket.utils.id_types import (
    CategoryId,
    MatchId,
    RoundId,
    StageId,
    StageItemId,
    StageItemInputId,
    TeamId,
    TournamentId,
)

NOW = datetime_utc.now()
TOURNAMENT_ID = TournamentId(1)
CATEGORY_ID = CategoryId(1)
ids = count(1)


def team(name: str) -> FullTeamWithPlayers:
    return FullTeamWithPlayers(
        id=TeamId(next(ids)),
        name=name,
        created=NOW,
        tournament_id=TOURNAMENT_ID,
        active=True,
        players=[],
        category_id=CATEGORY_ID,
    )


def final_input(
    stage_item_id: StageItemId, slot: int, team_: FullTeamWithPlayers
) -> StageItemInput:
    return StageItemInputFinal(
        id=StageItemInputId(next(ids)),
        slot=slot,
        tournament_id=TOURNAMENT_ID,
        stage_item_id=stage_item_id,
        team_id=team_.id,
        team=Team(**team_.model_dump(exclude={"players"})),
    )


def advancing_input(
    stage_item_id: StageItemId, slot: int, source: StageItemWithRounds, position: int
) -> StageItemInput:
    return StageItemInputTentative(
        id=StageItemInputId(next(ids)),
        slot=slot,
        tournament_id=TOURNAMENT_ID,
        stage_item_id=stage_item_id,
        winner_from_stage_item_id=source.id,
        winner_position=position,
    )


def match(input1: StageItemInput | None, input2: StageItemInput | None) -> MatchWithDetails:
    return MatchWithDetails(
        id=MatchId(next(ids)),
        created=NOW,
        duration_minutes=10,
        margin_minutes=5,
        round_id=RoundId(1),
        stage_item_input1_id=input1.id if input1 else None,
        stage_item_input2_id=input2.id if input2 else None,
        stage_item_input1_score=0,
        stage_item_input2_score=0,
        stage_item_input1_conflict=False,
        stage_item_input2_conflict=False,
    )


def stage_item(
    stage_type: StageType,
    team_count: int,
    make_inputs: Callable[[StageItemId], list[StageItemInput]],
) -> StageItemWithRounds:
    """
    `make_inputs(stage_item_id)` returns the inputs. Round robin: every pair plays once.
    Knockout: the first round pairs inputs, later rounds don't have inputs yet.
    """
    stage_item_id = StageItemId(next(ids))
    inputs = make_inputs(stage_item_id)
    matches: list[MatchWithDetailsDefinitive | MatchWithDetails]
    if stage_type is StageType.ROUND_ROBIN:
        matches = [match(a, b) for a, b in combinations(inputs, 2)]
    else:
        matches = [match(inputs[i], inputs[i + 1]) for i in range(0, len(inputs), 2)]
        matches += [match(None, None) for _ in range(len(inputs) // 2 - 1)]
    return StageItemWithRounds(
        id=stage_item_id,
        stage_id=StageId(1),
        name="",
        created=NOW,
        type=stage_type,
        team_count=team_count,
        ranking_id=None,
        type_name="",
        inputs=inputs,
        rounds=[
            RoundWithMatches(
                id=RoundId(1),
                stage_item_id=stage_item_id,
                created=NOW,
                is_draft=False,
                name="",
                matches=matches,
            )
        ],
    )


def stage(*stage_items: StageItemWithRounds) -> StageWithStageItems:
    return StageWithStageItems(
        id=StageId(next(ids)),
        tournament_id=TOURNAMENT_ID,
        name="",
        created=NOW,
        is_active=False,
        category_id=CATEGORY_ID,
        stage_items=list(stage_items),
    )


def group(teams: list[FullTeamWithPlayers]) -> StageItemWithRounds:
    return stage_item(
        StageType.ROUND_ROBIN,
        len(teams),
        lambda id_: [final_input(id_, slot, t) for slot, t in enumerate(teams)],
    )


def final(
    group_a: StageItemWithRounds, group_b: StageItemWithRounds, position: int
) -> StageItemWithRounds:
    return stage_item(
        StageType.SINGLE_ELIMINATION,
        2,
        lambda id_: [
            advancing_input(id_, 0, group_a, position),
            advancing_input(id_, 1, group_b, position),
        ],
    )


def category(age: int | None, *, results_public: bool) -> Category:
    return Category(
        id=CATEGORY_ID,
        tournament_id=TOURNAMENT_ID,
        name="Class",
        created=NOW,
        age=age,
        results_public=results_public,
    )


def test_round_robin_group_of_four_guarantees_three_matches() -> None:
    teams = [team(f"Team {i}") for i in range(4)]
    group_a = group(teams)
    assert get_guaranteed_matches_per_stage_item([stage(group_a)]) == {group_a.id: 3}
    assert not get_category_warnings(category(10, results_public=False), teams, [stage(group_a)])


def test_knockout_guarantees_one_match() -> None:
    teams = [team(f"Team {i}") for i in range(4)]
    knockout = stage_item(
        StageType.SINGLE_ELIMINATION,
        4,
        lambda id_: [final_input(id_, slot, t) for slot, t in enumerate(teams)],
    )
    assert get_guaranteed_matches_per_stage_item([stage(knockout)]) == {knockout.id: 1}

    warnings = get_category_warnings(category(13, results_public=True), teams, [stage(knockout)])
    assert warnings == [
        CategoryWarning(
            code=CategoryWarningCode.TOO_FEW_MATCHES,
            minimum_matches=1,
            team_names=["Team 0", "Team 1", "Team 2", "Team 3"],
        )
    ]


def test_groups_of_three_with_placement_finals() -> None:
    """
    Two groups of 3 (2 matches each), then A, B and C finals between equal placings: every team
    plays 3 matches whatever its placing. Without the C final, the 3rd placed teams only play 2.
    """
    teams = [team(f"Team {i}") for i in range(6)]
    group_a, group_b = group(teams[:3]), group(teams[3:])
    finals = [final(group_a, group_b, position) for position in (1, 2, 3)]
    stages = [stage(group_a, group_b), stage(*finals)]

    guaranteed = get_guaranteed_matches_per_stage_item(stages)
    assert guaranteed[group_a.id] == guaranteed[group_b.id] == 3
    assert not get_category_warnings(category(12, results_public=False), teams, stages)

    stages_without_c_final = [stage(group_a, group_b), stage(*finals[:2])]
    assert get_guaranteed_matches_per_stage_item(stages_without_c_final)[group_a.id] == 2
    warnings = get_category_warnings(
        category(12, results_public=False), teams, stages_without_c_final
    )
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning.code is CategoryWarningCode.TOO_FEW_MATCHES
    assert warning.minimum_matches == 2
    # Any team can end up 3rd, so all of them are at risk
    assert warning.team_names == [t.name for t in teams]


def test_too_few_matches_only_checked_for_13_and_younger() -> None:
    teams = [team(f"Team {i}") for i in range(2)]
    stages = [stage(group(teams))]
    assert not get_category_warnings(category(14, results_public=True), teams, stages)
    assert not get_category_warnings(category(None, results_public=True), teams, stages)
    warnings = get_category_warnings(category(13, results_public=True), teams, stages)
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning.code is CategoryWarningCode.TOO_FEW_MATCHES


def test_unplaced_teams_and_public_children_results() -> None:
    placed = [team(f"Placed {i}") for i in range(4)]
    unplaced = team("Not placed")
    inactive = team("Inactive").model_copy(update={"active": False})
    warnings = get_category_warnings(
        category(9, results_public=True), [*placed, unplaced, inactive], [stage(group(placed))]
    )
    assert warnings == [
        CategoryWarning(code=CategoryWarningCode.CHILDREN_RESULTS_PUBLIC),
        CategoryWarning(code=CategoryWarningCode.UNPLACED_TEAMS, team_names=["Not placed"]),
    ]
