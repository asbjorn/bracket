"""
Entering results with a score link: no account, only the token of the link. A link is bound
to a tournament and optionally to one court; only those matches can be seen and changed.
"""

from fastapi import HTTPException
from starlette import status

from bracket.logic.match_results import save_match
from bracket.models.db.match import MatchWithDetails, MatchWithDetailsDefinitive
from bracket.models.db.score_link import (
    ScoreEntryBody,
    ScoreEntryMatch,
    ScoreEntryView,
    ScoreLink,
)
from bracket.models.db.stage_item_inputs import StageItemInput, StageItemInputFinal
from bracket.models.db.tournament import TournamentStatus
from bracket.sql.categories import get_all_categories_in_tournament
from bracket.sql.courts import get_all_courts_in_tournament
from bracket.sql.score_links import get_valid_score_link
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.tournaments import sql_get_tournament
from bracket.utils.id_types import MatchId, TeamId


async def score_link_dependency(token: str) -> ScoreLink:
    link = await get_valid_score_link(token)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This link is not valid (any more). Ask the organiser for a new one.",
        )
    return link


def team_of(input_: StageItemInput | None) -> tuple[TeamId | None, str | None]:
    if isinstance(input_, StageItemInputFinal):
        return input_.team.id, input_.team.name
    return None, None


async def get_link_matches(
    link: ScoreLink,
) -> list[tuple[ScoreEntryMatch, MatchWithDetails | MatchWithDetailsDefinitive]]:
    """The scheduled matches the link gives access to, in order of time."""
    stages = await get_full_tournament_details(link.tournament_id)
    categories = {c.id: c.name for c in await get_all_categories_in_tournament(link.tournament_id)}
    courts = {c.id: c.name for c in await get_all_courts_in_tournament(link.tournament_id)}

    result = []
    for stage in stages:
        for stage_item in stage.stage_items:
            for round_ in stage_item.rounds:
                for match in round_.matches:
                    if match.start_time is None or match.court_id is None:
                        continue
                    if link.court_id is not None and match.court_id != link.court_id:
                        continue
                    team1_id, team1_name = team_of(match.stage_item_input1)
                    team2_id, team2_name = team_of(match.stage_item_input2)
                    entry = ScoreEntryMatch(
                        id=match.id,
                        round_id=match.round_id,
                        court_id=match.court_id,
                        court_name=courts.get(match.court_id),
                        start_time=match.start_time,
                        duration_minutes=match.duration_minutes,
                        category_name=(
                            categories.get(stage.category_id)
                            if stage.category_id is not None
                            else None
                        ),
                        stage_item_name=stage_item.name,
                        team1_id=team1_id,
                        team1_name=team1_name,
                        team2_id=team2_id,
                        team2_name=team2_name,
                        score1=match.stage_item_input1_score,
                        score2=match.stage_item_input2_score,
                        penalties1=match.stage_item_input1_penalties,
                        penalties2=match.stage_item_input2_penalties,
                        played=match.played,
                        result_type=match.result_type,
                    )
                    result.append((entry, match))
    result.sort(key=lambda pair: (pair[0].start_time, pair[0].court_name or "", pair[0].id))
    return result


async def get_score_entry_view(link: ScoreLink) -> ScoreEntryView:
    tournament = await sql_get_tournament(link.tournament_id)
    courts = {c.id: c.name for c in await get_all_courts_in_tournament(link.tournament_id)}
    return ScoreEntryView(
        tournament_name=tournament.name,
        link_name=link.name,
        court_id=link.court_id,
        court_name=courts.get(link.court_id) if link.court_id is not None else None,
        expires_at=link.expires_at,
        matches=[entry for entry, _ in await get_link_matches(link)],
    )


async def enter_result(link: ScoreLink, match_id: MatchId, body: ScoreEntryBody) -> None:
    tournament = await sql_get_tournament(link.tournament_id)
    if tournament.status is TournamentStatus.ARCHIVED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The tournament is archived")

    found = next((pair for pair in await get_link_matches(link) if pair[0].id == match_id), None)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This match can't be entered with this link")
    entry, match = found
    if entry.team1_id is None or entry.team2_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "The teams of this match are not known yet"
        )

    match_body = body.to_match_body(
        match.round_id, match.court_id, match.custom_duration_minutes, match.custom_margin_minutes
    )
    await save_match(link.tournament_id, match, match_body)
