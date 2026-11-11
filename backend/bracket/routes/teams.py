import csv
import os
from uuid import uuid4

import aiofiles
import aiofiles.os
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from heliclockter import datetime_utc
from starlette import status

from bracket.config import config
from bracket.database import database
from bracket.logic.results_visibility import hide_team_statistics_of_private_categories
from bracket.logic.subscriptions import check_requirement
from bracket.logic.teams import get_team_logo_path
from bracket.logic.walkovers import set_team_flag, withdraw_team
from bracket.models.db.player import PlayerBody
from bracket.models.db.score_link import CheckInBody
from bracket.models.db.team import (
    FullTeamWithPlayers,
    Team,
    TeamBody,
    TeamInsertable,
    TeamMultiBody,
)
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import (
    user_authenticated_for_tournament,
    user_authenticated_or_public_dashboard,
)
from bracket.routes.models import (
    CountResponse,
    PaginatedTeams,
    SingleTeamResponse,
    SuccessResponse,
    TeamsWithPlayersResponse,
)
from bracket.routes.util import (
    disallow_archived_tournament,
    team_dependency,
    team_with_players_dependency,
)
from bracket.schema import players_x_teams, teams
from bracket.sql.categories import get_all_categories_in_tournament
from bracket.sql.players import get_all_players_in_tournament, insert_player
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.teams import (
    get_team_by_id,
    get_team_count,
    get_teams_with_members,
    sql_delete_team,
)
from bracket.sql.validation import check_foreign_keys_belong_to_tournament
from bracket.utils.db import fetch_one_parsed
from bracket.utils.errors import ForeignKey, check_foreign_key_violation
from bracket.utils.id_types import CategoryId, PlayerId, TeamId, TournamentId
from bracket.utils.logging import logger
from bracket.utils.pagination import PaginationTeams
from bracket.utils.types import assert_some

router = APIRouter(prefix=config.api_prefix)


async def update_team_members(
    team_id: TeamId, tournament_id: TournamentId, player_ids: set[PlayerId]
) -> None:
    [team] = await get_teams_with_members(tournament_id, team_id=team_id)

    # Add members to the team
    for player_id in player_ids:
        if player_id not in team.player_ids:
            await database.execute(
                query=players_x_teams.insert(),
                values={"team_id": team_id, "player_id": player_id},
            )

    # Remove old members from the team
    await database.execute(
        query=players_x_teams.delete().where(
            (players_x_teams.c.player_id.not_in(player_ids))  # type: ignore[attr-defined]
            & (players_x_teams.c.team_id == team_id)
        ),
    )


@router.get("/tournaments/{tournament_id}/teams", response_model=TeamsWithPlayersResponse)
async def get_teams(
    tournament_id: TournamentId,
    pagination: PaginationTeams = Depends(),
    category_id: CategoryId | None = None,
    user: UserPublic | None = Depends(user_authenticated_or_public_dashboard),
) -> TeamsWithPlayersResponse:
    """
    Returns the teams of the tournament, optionally only those of one age class (`category_id`).
    """
    teams_ = await get_teams_with_members(
        tournament_id, pagination=pagination, category_id=category_id
    )
    if user is None:
        # Public dashboard: don't reveal results of classes where that's not allowed
        categories = await get_all_categories_in_tournament(tournament_id)
        teams_ = hide_team_statistics_of_private_categories(teams_, categories)

    return TeamsWithPlayersResponse(
        data=PaginatedTeams(
            teams=teams_,
            count=await get_team_count(tournament_id, category_id=category_id),
        )
    )


async def check_team_can_change_category(team: Team, new_category_id: CategoryId | None) -> None:
    """
    A team that is already placed in a stage can't move to another age class, because stages
    only contain teams of their own class.
    """
    if team.category_id == new_category_id:
        return

    stages = await get_full_tournament_details(team.tournament_id)
    if any(
        input_.team_id == team.id
        for stage in stages
        for stage_item in stage.stage_items
        for input_ in stage_item.inputs
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team is placed in a stage of its class, remove it there first",
        )


@router.put("/tournaments/{tournament_id}/teams/{team_id}", response_model=SingleTeamResponse)
async def update_team_by_id(
    tournament_id: TournamentId,
    team_body: TeamBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
    team: Team = Depends(team_dependency),
) -> SingleTeamResponse:
    await check_foreign_keys_belong_to_tournament(team_body, tournament_id)
    await check_team_can_change_category(team, team_body.category_id)

    await database.execute(
        query=teams.update().where(
            (teams.c.id == team.id) & (teams.c.tournament_id == tournament_id)
        ),
        values=team_body.model_dump(exclude={"player_ids"}),
    )
    await update_team_members(team.id, tournament_id, team_body.player_ids)

    return SingleTeamResponse(
        data=assert_some(
            await fetch_one_parsed(
                database,
                Team,
                teams.select().where(
                    (teams.c.id == team.id) & (teams.c.tournament_id == tournament_id)
                ),
            )
        )
    )


@router.post("/tournaments/{tournament_id}/teams/{team_id}/logo", response_model=SingleTeamResponse)
async def update_team_logo(
    tournament_id: TournamentId,
    file: UploadFile | None = None,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
    team: Team = Depends(team_dependency),
) -> SingleTeamResponse:
    old_logo_path = await get_team_logo_path(tournament_id, team.id)
    filename: str | None = None
    new_logo_path: str | None = None

    if file:
        assert file.filename is not None
        extension = os.path.splitext(file.filename)[1]
        assert extension in (".png", ".jpg", ".jpeg")

        filename = f"{uuid4()}{extension}"
        new_logo_path = f"static/team-logos/{filename}" if file is not None else None

        if new_logo_path:
            await aiofiles.os.makedirs("static/team-logos", exist_ok=True)
            async with aiofiles.open(new_logo_path, "wb") as f:
                await f.write(await file.read())

    if old_logo_path is not None and old_logo_path != new_logo_path:
        try:
            await aiofiles.os.remove(old_logo_path)
        except Exception as exc:
            logger.error(f"Could not remove logo that should still exist: {old_logo_path}\n{exc}")

    await database.execute(
        teams.update().where(teams.c.id == team.id),
        values={"logo_path": filename},
    )
    return SingleTeamResponse(data=assert_some(await get_team_by_id(team.id, tournament_id)))


@router.delete("/tournaments/{tournament_id}/teams/{team_id}", response_model=SuccessResponse)
async def delete_team(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
    team: FullTeamWithPlayers = Depends(team_with_players_dependency),
) -> SuccessResponse:
    with check_foreign_key_violation(
        {
            ForeignKey.stage_item_inputs_team_id_fkey,
            ForeignKey.matches_stage_item_input1_id_fkey,
            ForeignKey.matches_stage_item_input2_id_fkey,
        }
    ):
        await sql_delete_team(tournament_id, team.id)

    return SuccessResponse()


@router.post("/tournaments/{tournament_id}/teams/{team_id}/withdraw", response_model=CountResponse)
async def withdraw_team_from_tournament(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
    team: Team = Depends(team_dependency),
) -> CountResponse:
    """
    The team withdraws: its opponents get a walkover in all matches it hasn't played yet; the
    schedule stays as it is. Returns the number of matches given as walkover.
    """
    return CountResponse(data=await withdraw_team(tournament_id, team.id))


@router.post(
    "/tournaments/{tournament_id}/teams/{team_id}/reinstate", response_model=SuccessResponse
)
async def reinstate_team(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
    team: Team = Depends(team_dependency),
) -> SuccessResponse:
    """Undoes the withdrawal mark. Walkovers that were given stay; change them per match."""
    await set_team_flag(tournament_id, team.id, withdrawn=False)
    return SuccessResponse()


@router.put("/tournaments/{tournament_id}/teams/{team_id}/check_in", response_model=SuccessResponse)
async def check_in_team(
    tournament_id: TournamentId,
    body: CheckInBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    team: Team = Depends(team_dependency),
) -> SuccessResponse:
    await set_team_flag(tournament_id, team.id, checked_in=body.checked_in)
    return SuccessResponse()


@router.post("/tournaments/{tournament_id}/teams", response_model=SingleTeamResponse)
async def create_team(
    team_to_insert: TeamBody,
    tournament_id: TournamentId,
    user: UserPublic = Depends(user_authenticated_for_tournament),
    _: Tournament = Depends(disallow_archived_tournament),
) -> SingleTeamResponse:
    await check_foreign_keys_belong_to_tournament(team_to_insert, tournament_id)

    existing_teams = await get_teams_with_members(tournament_id)
    check_requirement(existing_teams, user, "max_teams")

    last_record_id = await database.execute(
        query=teams.insert(),
        values=TeamInsertable(
            **team_to_insert.model_dump(exclude={"player_ids"}),
            created=datetime_utc.now(),
            tournament_id=tournament_id,
        ).model_dump(),
    )
    await update_team_members(last_record_id, tournament_id, team_to_insert.player_ids)

    team_result = await get_team_by_id(last_record_id, tournament_id)
    assert team_result is not None
    return SingleTeamResponse(data=team_result)


@router.post("/tournaments/{tournament_id}/teams_multi", response_model=SuccessResponse)
async def create_multiple_teams(
    team_body: TeamMultiBody,
    tournament_id: TournamentId,
    user: UserPublic = Depends(user_authenticated_for_tournament),
    _: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    await check_foreign_keys_belong_to_tournament(team_body, tournament_id)
    reader = list(csv.reader(team_body.names.split("\n"), delimiter=","))
    teams_and_players = [
        (row[0], [p for p in row[1:] if len(p) > 0] if len(row) > 1 else [])
        for row in reader
        if len(row) > 0
    ]
    players = [player for row in teams_and_players for player in row[1]]

    existing_teams = await get_teams_with_members(tournament_id)
    existing_players = await get_all_players_in_tournament(tournament_id)

    check_requirement(existing_teams, user, "max_teams", additions=len(reader))
    check_requirement(existing_players, user, "max_players", additions=len(players))

    async with database.transaction():
        for team_name, players in teams_and_players:
            await database.execute(
                query=teams.insert(),
                values=TeamInsertable(
                    name=team_name,
                    active=team_body.active,
                    created=datetime_utc.now(),
                    tournament_id=tournament_id,
                    category_id=team_body.category_id,
                ).model_dump(),
            )
            for player in players:
                player_body = PlayerBody(name=player, active=team_body.active)
                await insert_player(player_body, tournament_id)

    return SuccessResponse()
