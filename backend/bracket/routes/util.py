from fastapi import HTTPException
from starlette import status

from bracket.database import database
from bracket.models.db.match import Match
from bracket.models.db.round import Round
from bracket.models.db.team import FullTeamWithPlayers, Team
from bracket.models.db.tournament import Tournament, TournamentStatus
from bracket.models.db.util import RoundWithMatches, StageItemWithRounds, StageWithStageItems
from bracket.schema import teams
from bracket.sql.rounds import get_round_by_id
from bracket.sql.stage_items import get_stage_item
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.teams import get_teams_with_members
from bracket.sql.tournaments import sql_get_tournament
from bracket.utils.db import fetch_one_parsed
from bracket.utils.id_types import MatchId, RoundId, StageId, StageItemId, TeamId, TournamentId

# Rounds and matches belong to a tournament via their stage item and stage
ROUND_IN_TOURNAMENT = """
    rounds.stage_item_id IN (
        SELECT stage_items.id
        FROM stage_items
        JOIN stages ON stages.id = stage_items.stage_id
        WHERE stages.tournament_id = :tournament_id
    )
"""


async def round_dependency(tournament_id: TournamentId, round_id: RoundId) -> Round:
    result = await database.fetch_one(
        f"SELECT rounds.* FROM rounds WHERE rounds.id = :round_id AND {ROUND_IN_TOURNAMENT}",
        values={"round_id": round_id, "tournament_id": tournament_id},
    )
    round_ = Round.model_validate(dict(result._mapping)) if result is not None else None

    if round_ is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find round with id {round_id}",
        )

    return round_


async def round_with_matches_dependency(
    tournament_id: TournamentId, round_id: RoundId
) -> RoundWithMatches:
    await round_dependency(tournament_id, round_id)  # 404 instead of an error
    return await get_round_by_id(tournament_id, round_id)


async def stage_dependency(tournament_id: TournamentId, stage_id: StageId) -> StageWithStageItems:
    stages_result = await get_full_tournament_details(
        tournament_id, no_draft_rounds=False, stage_id=stage_id
    )

    if len(stages_result) < 1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find stage with id {stage_id}",
        )

    return stages_result[0]


async def stage_item_dependency(
    tournament_id: TournamentId, stage_item_id: StageItemId
) -> StageItemWithRounds:
    return await get_stage_item(tournament_id, stage_item_id=stage_item_id)


async def match_dependency(tournament_id: TournamentId, match_id: MatchId) -> Match:
    result = await database.fetch_one(
        f"""
        SELECT matches.*
        FROM matches
        JOIN rounds ON rounds.id = matches.round_id
        WHERE matches.id = :match_id AND {ROUND_IN_TOURNAMENT}
        """,
        values={"match_id": match_id, "tournament_id": tournament_id},
    )
    match = Match.model_validate(dict(result._mapping)) if result is not None else None

    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find match with id {match_id}",
        )

    return match


async def team_dependency(tournament_id: TournamentId, team_id: TeamId) -> Team:
    team = await fetch_one_parsed(
        database,
        Team,
        teams.select().where((teams.c.id == team_id) & (teams.c.tournament_id == tournament_id)),
    )

    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find team with id {team_id}",
        )

    return team


async def team_with_players_dependency(
    tournament_id: TournamentId, team_id: TeamId
) -> FullTeamWithPlayers:
    teams_with_members = await get_teams_with_members(tournament_id, team_id=team_id)

    if len(teams_with_members) < 1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find team with id {team_id}",
        )

    return teams_with_members[0]


async def disallow_archived_tournament(tournament_id: TournamentId) -> Tournament:
    tournament = await sql_get_tournament(tournament_id)
    if tournament.status is TournamentStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can't update archived tournament",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return tournament
