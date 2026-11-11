import pytest

from bracket.database import database
from bracket.logic.scheduling.cup_setup import group_letter
from bracket.models.db.stage_item import StageType
from bracket.models.db.stage_item_inputs import StageItemInputTentative
from bracket.schema import categories, courts, time_windows
from bracket.sql.categories import get_category_by_id
from bracket.sql.courts import get_all_courts_in_tournament
from bracket.sql.shared import sql_delete_stage_item_with_foreign_keys
from bracket.sql.stages import get_full_tournament_details, sql_delete_stage
from bracket.sql.time_windows import get_time_windows
from bracket.utils.http import HTTPMethod
from bracket.utils.types import JsonDict, assert_some
from tests.integration_tests.api.shared import SUCCESS_RESPONSE, send_tournament_request
from tests.integration_tests.models import AuthContext

G10 = {"name": "G10", "age": 10, "team_count": 6, "group_size": 3, "duration_minutes": 10}
G10 |= {"game_format": "7v7"}
J14 = {
    "name": "J14",
    "age": 14,
    "team_count": 8,
    "group_size": 4,
    "playoffs": "AB",
    "third_place_match": True,
    "duration_minutes": 15,
    "margin_minutes": 3,
    "game_format": "9v9",
}
NAMES = {"group_stage": "Gruppespill", "group": "Gruppe", "playoff_stage": "Sluttspill"}
NAMES |= {"playoff": "{}-sluttspill"}
WINDOW = {"start_time": "2026-06-13T07:00:00Z", "end_time": "2026-06-13T15:00:00Z"}


async def delete_cup(auth_context: AuthContext) -> None:
    tournament_id = auth_context.tournament.id
    stages = await get_full_tournament_details(tournament_id)
    # Later stages first: their inputs refer to the groups of earlier stages
    for stage in sorted(stages, key=lambda stage: stage.id, reverse=True):
        for stage_item in stage.stage_items:
            await sql_delete_stage_item_with_foreign_keys(stage_item.id)
        await sql_delete_stage(tournament_id, stage.id)
    await database.execute(categories.delete().where(categories.c.tournament_id == tournament_id))
    await database.execute(courts.delete().where(courts.c.tournament_id == tournament_id))
    await database.execute(
        time_windows.delete().where(time_windows.c.tournament_id == tournament_id)
    )


def test_group_letters() -> None:
    assert [group_letter(i) for i in (0, 1, 25, 26, 27, 51, 52)] == [
        "A",
        "B",
        "Z",
        "AA",
        "AB",
        "AZ",
        "BA",
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_cup_setup_creates_everything(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    tournament_id = auth_context.tournament.id
    body: JsonDict = {
        "classes": [G10, J14],
        "courts": [
            {"count": 2, "name_prefix": "Bane", "game_format": "7v7"},
            {"count": 1, "name_prefix": "Bane", "game_format": "9v9"},
        ],
        "time_windows": [WINDOW],
        "names": NAMES,
    }
    try:
        response = await send_tournament_request(
            HTTPMethod.POST, "cup_setup", auth_context, json=body
        )
        assert response == SUCCESS_RESPONSE

        stages = sorted(await get_full_tournament_details(tournament_id), key=lambda s: s.id)
        assert [(s.name, len(s.stage_items)) for s in stages] == [
            ("Gruppespill", 2),  # G10: 6 teams in groups of 3
            ("Gruppespill", 2),  # J14: 8 teams in groups of 4
            ("Sluttspill", 2),  # J14: A and B
        ]
        g10_groups, j14_groups, j14_playoffs = (
            sorted(s.stage_items, key=lambda item: item.name) for s in stages
        )
        assert [(g.name, g.team_count, g.type) for g in g10_groups] == [
            ("Gruppe A", 3, StageType.ROUND_ROBIN),
            ("Gruppe B", 3, StageType.ROUND_ROBIN),
        ]
        g10_matches = [m for g in g10_groups for r in g.rounds for m in r.matches]
        assert len(g10_matches) == 6
        assert {m.duration_minutes for m in g10_matches} == {10}

        assert [(p.name, p.team_count) for p in j14_playoffs] == [
            ("A-sluttspill", 4),
            ("B-sluttspill", 4),
        ]
        a_playoff = j14_playoffs[0]
        assert {
            (input_.winner_from_stage_item_id, input_.winner_position)
            for input_ in a_playoff.inputs
            if isinstance(input_, StageItemInputTentative)
        } == {(group.id, placing) for group in j14_groups for placing in (1, 2)}
        # Semifinals, final and bronze final
        playoff_matches = [m for r in a_playoff.rounds for m in r.matches]
        assert len(playoff_matches) == 4
        assert {(m.duration_minutes, m.margin_minutes) for m in playoff_matches} == {(15, 3)}

        assert {stage.category_id for stage in stages[1:]} == {stages[2].category_id}
        g10 = await get_category_by_id(tournament_id, assert_some(stages[0].category_id))
        assert g10 is not None
        assert (g10.name, g10.results_public) == ("G10", False)

        assert [
            (c.name, c.game_format) for c in await get_all_courts_in_tournament(tournament_id)
        ] == [
            ("Bane 1", "7v7"),
            ("Bane 2", "7v7"),
            ("Bane 3", "9v9"),
        ]
        assert len(await get_time_windows(tournament_id)) == 1

        # The created cup can be planned: 6 + 12 group matches, 8 playoff matches, 07-15 UTC
        proposal = await send_tournament_request(HTTPMethod.POST, "schedule/apply", auth_context)
        assert proposal["data"]["matches_total"] == 26
        assert proposal["data"]["unscheduled_match_ids"] == []

        # Only once: a second run would duplicate the cup
        again = await send_tournament_request(HTTPMethod.POST, "cup_setup", auth_context, json=body)
        assert again == {
            "detail": "The setup wizard only works for a tournament without classes and stages"
        }
    finally:
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_cup_setup_rejects_playoffs_with_hidden_results(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    body: JsonDict = {"classes": [G10 | {"playoffs": "A"}], "time_windows": []}
    try:
        response = await send_tournament_request(
            HTTPMethod.POST, "cup_setup", auth_context, json=body
        )
        assert "aren't possible when the results of the class are hidden" in str(response)
        # Nothing was created
        assert await get_full_tournament_details(auth_context.tournament.id) == []
    finally:
        await delete_cup(auth_context)


@pytest.mark.asyncio(loop_scope="session")
async def test_cup_setup_rejects_duplicate_class_names(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    body: JsonDict = {"classes": [J14, J14 | {"name": "J14 "}], "time_windows": []}
    try:
        response = await send_tournament_request(
            HTTPMethod.POST, "cup_setup", auth_context, json=body
        )
        assert "Each class needs its own name" in str(response)
        assert await get_full_tournament_details(auth_context.tournament.id) == []
    finally:
        await delete_cup(auth_context)
