"""
Walkovers and withdrawn teams. A walkover is a played match with result type WALKOVER: the
team that showed up wins by the tournament's `walkover_goals` to 0. A withdrawn team loses all
its remaining matches that way; the schedule stays as it is.
"""

from fastapi import HTTPException
from starlette import status

from bracket.database import database
from bracket.logic.match_results import save_match
from bracket.models.db.match import (
    MatchBody,
    MatchResultType,
    MatchWithDetails,
    MatchWithDetailsDefinitive,
)
from bracket.models.db.stage_item_inputs import StageItemInput, StageItemInputFinal
from bracket.schema import teams
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.tournaments import sql_get_tournament
from bracket.utils.id_types import MatchId, TeamId, TournamentId

AnyMatch = MatchWithDetails | MatchWithDetailsDefinitive


def team_of(input_: StageItemInput | None) -> tuple[TeamId | None, str | None]:
    """The id and name of the team of an input, if it's known."""
    if isinstance(input_, StageItemInputFinal):
        return input_.team.id, input_.team.name
    return None, None


def team_ids_of(match: AnyMatch) -> tuple[TeamId | None, TeamId | None]:
    return team_of(match.stage_item_input1)[0], team_of(match.stage_item_input2)[0]


async def get_all_matches(tournament_id: TournamentId) -> list[AnyMatch]:
    return [
        match
        for stage in await get_full_tournament_details(tournament_id)
        for stage_item in stage.stage_items
        for round_ in stage_item.rounds
        for match in round_.matches
    ]


def walkover_body(match: AnyMatch, winner_team_id: TeamId, goals: int) -> MatchBody:
    team1, team2 = team_ids_of(match)
    if None in (team1, team2) or winner_team_id not in (team1, team2):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "The winner of a walkover must be one of the two teams"
        )
    team1_wins = winner_team_id == team1
    return MatchBody(
        round_id=match.round_id,
        court_id=match.court_id,
        custom_duration_minutes=match.custom_duration_minutes,
        custom_margin_minutes=match.custom_margin_minutes,
        stage_item_input1_score=goals if team1_wins else 0,
        stage_item_input2_score=0 if team1_wins else goals,
        result_type=MatchResultType.WALKOVER,
        stage_item_input1_penalties=None,
        stage_item_input2_penalties=None,
        played=True,
    )


async def record_walkover(
    tournament_id: TournamentId, match: AnyMatch, winner_team_id: TeamId
) -> None:
    tournament = await sql_get_tournament(tournament_id)
    body = walkover_body(match, winner_team_id, tournament.walkover_goals)
    await save_match(tournament_id, match, body)


async def record_walkover_by_id(
    tournament_id: TournamentId, match_id: MatchId, winner_team_id: TeamId
) -> None:
    match = next((m for m in await get_all_matches(tournament_id) if m.id == match_id), None)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Could not find match with id {match_id}")
    await record_walkover(tournament_id, match, winner_team_id)


async def set_team_flag(
    tournament_id: TournamentId,
    team_id: TeamId,
    *,
    withdrawn: bool | None = None,
    checked_in: bool | None = None,
) -> None:
    values = {
        key: value
        for key, value in {"withdrawn": withdrawn, "checked_in": checked_in}.items()
        if value is not None
    }
    await database.execute(
        teams.update().where((teams.c.id == team_id) & (teams.c.tournament_id == tournament_id)),
        values=values,
    )


async def withdraw_team(tournament_id: TournamentId, team_id: TeamId) -> int:
    """
    Marks the team as withdrawn and gives its opponents a walkover in every match that isn't
    played yet. Returns the number of matches. Matches whose opponent isn't known yet (later
    knockout rounds) or is withdrawn too stay open.
    """
    tournament = await sql_get_tournament(tournament_id)
    async with database.transaction():
        await set_team_flag(tournament_id, team_id, withdrawn=True)
        withdrawn_teams = {
            row["id"]
            for row in await database.fetch_all(
                "SELECT id FROM teams WHERE tournament_id = :id AND withdrawn",
                values={"id": tournament_id},
            )
        }
        count = 0
        for match in await get_all_matches(tournament_id):
            team1, team2 = team_ids_of(match)
            if match.played or team_id not in (team1, team2):
                continue
            opponent = team2 if team1 == team_id else team1
            if opponent is None or opponent in withdrawn_teams:
                continue
            body = walkover_body(match, opponent, tournament.walkover_goals)
            await save_match(tournament_id, match, body)
            count += 1
    return count
