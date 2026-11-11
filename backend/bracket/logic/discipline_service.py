"""
Loads and checks what the discipline rules (`logic/discipline.py`) need: which teams play
which matches, in which class, and whether that class has discipline at all.
"""

from dataclasses import dataclass

from fastapi import HTTPException
from starlette import status

from bracket.database import database
from bracket.logic.discipline import TeamMatch, compute_suspensions, discipline_allowed
from bracket.models.db.discipline import (
    DisciplineOverview,
    JuryDecisionBody,
    MatchCardBody,
    SuspendedPlayer,
)
from bracket.models.db.stage_item_inputs import StageItemInputFinal
from bracket.sql.categories import get_all_categories_in_tournament
from bracket.sql.discipline import (
    get_cards,
    get_discipline_settings,
    get_jury_decisions,
)
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.teams import get_team_by_id
from bracket.utils.id_types import MatchId, TeamId, TournamentId


@dataclass(frozen=True)
class MatchInfo:
    team_ids: frozenset[TeamId]
    allowed: bool  # The class of the match has discipline


async def get_matches_of_teams(
    tournament_id: TournamentId,
) -> tuple[dict[MatchId, MatchInfo], dict[TeamId, list[TeamMatch]]]:
    categories = {c.id: c for c in await get_all_categories_in_tournament(tournament_id)}
    matches: dict[MatchId, MatchInfo] = {}
    team_matches: dict[TeamId, list[TeamMatch]] = {}
    for stage in await get_full_tournament_details(tournament_id):
        category = categories.get(stage.category_id) if stage.category_id is not None else None
        allowed = discipline_allowed(category)
        for stage_item in stage.stage_items:
            for round_ in stage_item.rounds:
                for match in round_.matches:
                    team_ids = frozenset(
                        input_.team.id
                        for input_ in (match.stage_item_input1, match.stage_item_input2)
                        if isinstance(input_, StageItemInputFinal)
                    )
                    matches[match.id] = MatchInfo(team_ids, allowed)
                    for team_id in team_ids:
                        team_matches.setdefault(team_id, []).append(
                            TeamMatch(match.id, match.start_time)
                        )
    return matches, team_matches


async def get_discipline_overview(tournament_id: TournamentId) -> DisciplineOverview:
    settings = await get_discipline_settings(tournament_id)
    cards = await get_cards(tournament_id)
    decisions = await get_jury_decisions(tournament_id)
    _, team_matches = await get_matches_of_teams(tournament_id)
    return DisciplineOverview(
        settings=settings,
        cards=cards,
        suspensions=compute_suspensions(
            cards,
            team_matches,
            settings.suspension_matches_per_red,
            settings.yellow_cards_for_suspension,
            decisions,
        ),
        decisions=decisions,
    )


async def get_suspended_players(
    tournament_id: TournamentId,
) -> dict[MatchId, list[SuspendedPlayer]]:
    overview = await get_discipline_overview(tournament_id)
    result: dict[MatchId, list[SuspendedPlayer]] = {}
    for suspension in overview.suspensions:
        for match_id in suspension.match_ids:
            result.setdefault(match_id, []).append(
                SuspendedPlayer(team_id=suspension.team_id, player_name=suspension.player_name)
            )
    return result


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail)


async def check_card(tournament_id: TournamentId, match_id: MatchId, body: MatchCardBody) -> None:
    matches, _ = await get_matches_of_teams(tournament_id)
    match = matches.get(match_id)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the match")
    if not match.allowed:
        raise bad_request("Cards are only kept for classes from 13 years with public results")
    if body.team_id not in match.team_ids:
        raise bad_request("This team doesn't play in this match")
    if body.player_id is not None:
        # The player must be in this tournament and in the team that gets the card
        in_team = await database.fetch_val(
            """
            SELECT count(*)
            FROM players_x_teams pt
            JOIN players p ON p.id = pt.player_id
            WHERE pt.player_id = :player_id AND pt.team_id = :team_id
            AND p.tournament_id = :tournament_id
            """,
            values={
                "player_id": body.player_id,
                "team_id": body.team_id,
                "tournament_id": tournament_id,
            },
        )
        if not in_team:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the player in this team")


async def check_jury_decision(tournament_id: TournamentId, body: JuryDecisionBody) -> None:
    """The match, team and card of a decision must belong to the tournament."""
    if body.card_id is not None and body.card_id not in {
        card.id for card in await get_cards(tournament_id)
    }:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the card")
    if (
        body.match_id is not None
        and body.match_id not in (await get_matches_of_teams(tournament_id))[0]
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the match")
    if body.team_id is not None and await get_team_by_id(body.team_id, tournament_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the team")
    if body.suspension_change != 0 and body.card_id is None:
        raise bad_request("Choose the card whose suspension changes")
