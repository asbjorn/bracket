import pytest

from bracket.models.db.stage_item import StageType
from bracket.models.db.stage_item_inputs import StageItemInputTentative
from bracket.models.db.util import StageWithStageItems
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.http import HTTPMethod
from bracket.utils.types import JsonDict, assert_some
from tests.integration_tests.api.cup_setup_test import G10, J14, NAMES, delete_cup
from tests.integration_tests.api.final_results_test import play_all
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
from tests.integration_tests.models import AuthContext


async def set_up(auth_context: AuthContext, j14_teams: int) -> None:
    """G10 (2 groups of 3) and J14 (2 groups of 4, A/B playoffs with third place)."""
    body: JsonDict = {"classes": [G10, J14], "time_windows": [], "names": NAMES}
    response = await send_tournament_request(HTTPMethod.POST, "cup_setup", auth_context, json=body)
    assert response == SUCCESS_RESPONSE
    stages = sorted(
        await get_full_tournament_details(auth_context.tournament.id), key=lambda s: s.id
    )
    j14_id = assert_some(stages[1].category_id)
    names = "\n".join(f"Lag {index}" for index in range(1, j14_teams + 1))
    response = await send_tournament_request(
        HTTPMethod.POST,
        "teams_multi",
        auth_context,
        json={"names": names, "active": True, "category_id": j14_id},
    )
    assert response == SUCCESS_RESPONSE


@pytest.mark.asyncio(loop_scope="session")
async def test_fit_groups(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    try:
        await set_up(auth_context, j14_teams=10)
        stages = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        g10_stage, j14_stage = stages[0], stages[1]
        endpoint = f"stages/{j14_stage.id}/fit_groups?group_size=4"

        preview = await send_tournament_request(HTTPMethod.GET, endpoint, auth_context)
        assert preview == {
            "data": {
                "team_count": 10,
                "current_group_sizes": [4, 4],
                "group_sizes": [4, 3, 3],
                "matches_per_team_min": 2,
                "matches_per_team_max": 3,
                # Groups 6 + 3 + 3, A playoff of 6 with third place 6, B playoff of 3: 2
                "match_count": 20,
                "playoffs": [
                    {"name": "A-sluttspill", "team_count": 6},
                    {"name": "B-sluttspill", "team_count": 3},
                ],
                "removed_playoffs": [],
                "planned_match_count": 0,
                "groups_rebuilt": True,
            }
        }
        # A preview changes nothing
        unchanged = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        assert [len(stage.stage_items) for stage in unchanged] == [2, 2, 2]

        applied = await send_tournament_request(HTTPMethod.POST, endpoint, auth_context)
        assert applied == preview

        stages = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        assert len(stages) == 3
        [g10, j14, playoffs] = stages
        assert g10 == g10_stage  # Other classes are untouched
        assert j14.id == j14_stage.id and j14.is_active
        groups = sorted(j14.stage_items, key=lambda item: item.name)
        assert [(g.name, g.team_count, g.type) for g in groups] == [
            ("Gruppe A", 4, StageType.ROUND_ROBIN),
            ("Gruppe B", 3, StageType.ROUND_ROBIN),
            ("Gruppe C", 3, StageType.ROUND_ROBIN),
        ]
        assert [sum(len(r.matches) for r in g.rounds) for g in groups] == [6, 3, 3]

        assert playoffs.name == "Sluttspill" and playoffs.category_id == j14.category_id
        items = sorted(playoffs.stage_items, key=lambda item: item.name)
        assert [(item.name, item.team_count) for item in items] == [
            ("A-sluttspill", 6),
            ("B-sluttspill", 3),
        ]
        group_ids = {group.id for group in groups}
        for item, placings in zip(items, ([1, 2], [3]), strict=True):
            inputs = [i for i in item.inputs if isinstance(i, StageItemInputTentative)]
            assert len(inputs) == len(item.inputs)
            assert {input_.winner_from_stage_item_id for input_ in inputs} == group_ids
            assert sorted({input_.winner_position for input_ in inputs}) == placings
        # A playoff of 6 keeps its match for third place: 5 matches + 1
        assert sum(len(r.matches) for r in items[0].rounds) == 6

        # Fitting again to smaller groups: the B playoff has no placing 3 left
        smaller = await send_tournament_request(
            HTTPMethod.POST, f"stages/{j14_stage.id}/fit_groups?group_size=2", auth_context
        )
        assert smaller["data"]["group_sizes"] == [2, 2, 2, 2, 2]
        assert smaller["data"]["playoffs"] == [{"name": "A-sluttspill", "team_count": 10}]
        assert smaller["data"]["removed_playoffs"] == ["B-sluttspill"]
    finally:
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_fit_groups_errors(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    try:
        await set_up(auth_context, j14_teams=8)
        stages = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        g10_stage, j14_stage, playoff_stage = stages

        no_teams = await send_tournament_request(
            HTTPMethod.GET, f"stages/{g10_stage.id}/fit_groups?group_size=3", auth_context
        )
        assert no_teams == {"detail": "The class needs at least 2 teams"}

        not_groups = await send_tournament_request(
            HTTPMethod.GET, f"stages/{playoff_stage.id}/fit_groups?group_size=3", auth_context
        )
        assert not_groups == {"detail": "Only a stage with round robin groups can be fitted"}

        too_big = await send_tournament_request(
            HTTPMethod.GET, f"stages/{j14_stage.id}/fit_groups?group_size=11", auth_context
        )
        assert too_big == {"detail": "A group has between 2 and 10 teams"}

        missing = await send_tournament_request(
            HTTPMethod.GET, "stages/999999/fit_groups?group_size=3", auth_context
        )
        assert missing == {"detail": "Could not find the stage"}

        # After the draw the groups have teams and stay as they are
        teams = await send_tournament_request(
            HTTPMethod.GET, f"teams?category_id={j14_stage.category_id}", auth_context
        )
        team_ids = [team["id"] for team in teams["data"]["teams"]]
        response = await send_tournament_request(
            HTTPMethod.POST, f"stages/{j14_stage.id}/draw", auth_context, json={"pots": [team_ids]}
        )
        assert len(response["data"]) == 8
        drawn = await send_tournament_request(
            HTTPMethod.POST, f"stages/{j14_stage.id}/fit_groups?group_size=3", auth_context
        )
        assert "The groups already have teams" in drawn["detail"]
        after = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        assert {item.id for item in after[1].stage_items} == {
            item.id for item in j14_stage.stage_items
        }

        # Results hidden (G10): no playoffs
        response = await send_tournament_request(
            HTTPMethod.POST,
            "teams_multi",
            auth_context,
            json={"names": "Lyn\nFana\nOs", "active": True, "category_id": g10_stage.category_id},
        )
        assert response == SUCCESS_RESPONSE
        hidden = await send_tournament_request(
            HTTPMethod.GET,
            f"stages/{g10_stage.id}/fit_groups?group_size=3&playoffs=A",
            auth_context,
        )
        assert "can't advance based on their placing" in hidden["detail"]

        # Once the playoffs have started, the format stays as it is
        await play_all(auth_context, j14_stage.id)
        response = await send_tournament_request(
            HTTPMethod.POST,
            "stages/activate",
            auth_context,
            json={"direction": "next", "category_id": j14_stage.category_id},
        )
        assert response == SUCCESS_RESPONSE
        started = await send_tournament_request(
            HTTPMethod.GET,
            f"stages/{j14_stage.id}/fit_groups?group_size=4&playoffs=A",
            auth_context,
        )
        assert started == {
            "detail": "The playoffs have started, so the format can't be changed any more"
        }
    finally:
        await delete_cup(auth_context)


async def draw_all(auth_context: AuthContext, stage_id: int, category_id: int) -> list[int]:
    teams = await send_tournament_request(
        HTTPMethod.GET, f"teams?category_id={category_id}", auth_context
    )
    team_ids = [team["id"] for team in teams["data"]["teams"]]
    response = await send_tournament_request(
        HTTPMethod.POST, f"stages/{stage_id}/draw", auth_context, json={"pots": [team_ids]}
    )
    assert len(response["data"]) == len(team_ids)
    return team_ids


@pytest.mark.asyncio(loop_scope="session")
async def test_change_playoffs(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    try:
        await set_up(auth_context, j14_teams=8)
        stages = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        j14_stage = stages[1]
        category_id = assert_some(j14_stage.category_id)
        await draw_all(auth_context, j14_stage.id, category_id)
        drawn = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)[1]

        # After the draw: one A playoff for everyone, the groups and their teams stay
        endpoint = f"stages/{j14_stage.id}/fit_groups?group_size=4&playoffs=A"
        preview = await send_tournament_request(HTTPMethod.GET, endpoint, auth_context)
        assert preview["data"]["groups_rebuilt"] is False
        assert preview["data"]["group_sizes"] == [4, 4]
        assert preview["data"]["playoffs"] == [{"name": "A-sluttspill", "team_count": 8}]
        assert preview["data"]["removed_playoffs"] == ["B-sluttspill"]
        await send_tournament_request(HTTPMethod.POST, endpoint, auth_context)
        stages = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        assert stages[1] == drawn
        assert [(item.name, item.team_count) for item in stages[2].stage_items] == [
            ("A-sluttspill", 8)
        ]

        # No playoffs: the playoff stage goes
        await send_tournament_request(
            HTTPMethod.POST,
            f"stages/{j14_stage.id}/fit_groups?group_size=4&playoffs=NONE",
            auth_context,
        )
        stages = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        assert len(stages) == 2

        # A and B with bronze finals: a new playoff stage with the given names
        response = await send_tournament_request(
            HTTPMethod.POST,
            f"stages/{j14_stage.id}/fit_groups?group_size=4&playoffs=AB&third_place_match=true"
            "&playoff_stage_name=Sluttspill&playoff_name=%7B%7D-finale",
            auth_context,
        )
        assert response["data"]["playoffs"] == [
            {"name": "A-finale", "team_count": 4},
            {"name": "B-finale", "team_count": 4},
        ]
        # 2 groups of 4 (12 matches), 2 playoffs of 4 with bronze finals (4 + 4)
        assert response["data"]["match_count"] == 20
        stages = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        assert stages[2].name == "Sluttspill"
        assert [sum(len(r.matches) for r in item.rounds) for item in stages[2].stage_items] == [
            4,
            4,
        ]
    finally:
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_move_team(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    try:
        await set_up(auth_context, j14_teams=7)
        stages = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        j14_stage = stages[1]
        await draw_all(auth_context, j14_stage.id, assert_some(j14_stage.category_id))

        def places(
            stage_id: int, stages: list[StageWithStageItems]
        ) -> dict[int, tuple[str, int | None]]:
            [stage] = [s for s in stages if s.id == stage_id]
            return {
                input_.id: (item.name, input_.team_id)
                for item in stage.stage_items
                for input_ in item.inputs
            }

        stages = await get_full_tournament_details(tournament_id)
        before = places(j14_stage.id, stages)
        empty = next(input_id for input_id, (_, team) in before.items() if team is None)
        empty_group = before[empty][0]
        team_place, (_, team) = next(
            (input_id, place)
            for input_id, place in before.items()
            if place[1] is not None and place[0] != empty_group
        )
        endpoint = f"stages/{j14_stage.id}/move_team"

        # To an empty place
        response = await send_tournament_request(
            HTTPMethod.POST,
            endpoint,
            auth_context,
            json={"team_id": team, "target_input_id": empty},
        )
        assert response == SUCCESS_RESPONSE
        after = places(j14_stage.id, await get_full_tournament_details(tournament_id))
        assert after[empty][1] == team and after[team_place][1] is None

        # Swapped with a team in another group
        other_place, (_, other) = next(
            (input_id, place)
            for input_id, place in after.items()
            if place[1] is not None and place[0] != empty_group
        )
        response = await send_tournament_request(
            HTTPMethod.POST,
            endpoint,
            auth_context,
            json={"team_id": team, "target_input_id": other_place},
        )
        assert response == SUCCESS_RESPONSE
        swapped = places(j14_stage.id, await get_full_tournament_details(tournament_id))
        assert swapped[other_place][1] == team and swapped[empty][1] == other

        # Not into a playoff, not a team from elsewhere, not after playing
        playoff_stage = sorted(
            await get_full_tournament_details(tournament_id), key=lambda s: s.id
        )[2]
        not_groups = await send_tournament_request(
            HTTPMethod.POST,
            f"stages/{playoff_stage.id}/move_team",
            auth_context,
            json={"team_id": team, "target_input_id": empty},
        )
        assert not_groups == {"detail": "Teams can only be moved between groups"}
        await play_all(auth_context, j14_stage.id)
        played = await send_tournament_request(
            HTTPMethod.POST,
            endpoint,
            auth_context,
            json={"team_id": team, "target_input_id": empty},
        )
        assert played == {"detail": "Teams that have played a match in this stage can't be moved"}
    finally:
        await delete_cup(auth_context)
