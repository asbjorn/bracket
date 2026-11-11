"""
Entering results with a score link: no account, only the token of the link. A link is bound
to a tournament and optionally to one court; only those matches can be seen and changed.
"""

from fastapi import HTTPException, Request
from starlette import status

from bracket.logic.discipline import discipline_allowed
from bracket.logic.discipline_service import check_card, get_suspended_players
from bracket.logic.match_results import save_match
from bracket.logic.walkovers import record_walkover, set_team_flag, team_of
from bracket.models.db.discipline import MatchCard, MatchCardBody
from bracket.models.db.match import MatchWithDetails, MatchWithDetailsDefinitive
from bracket.models.db.official import MatchOfficialRole
from bracket.models.db.score_link import (
    ScoreEntryBody,
    ScoreEntryMatch,
    ScoreEntryView,
    ScoreLink,
)
from bracket.models.db.stage_item_inputs import StageItemInputFinal
from bracket.models.db.tournament import TournamentStatus
from bracket.sql.categories import get_all_categories_in_tournament
from bracket.sql.courts import get_all_courts_in_tournament
from bracket.sql.discipline import get_cards, sql_create_card, sql_delete_card
from bracket.sql.matches import sql_set_match_started
from bracket.sql.officials import get_public_match_officials
from bracket.sql.score_links import get_valid_score_link
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.tournaments import sql_get_tournament
from bracket.utils.id_types import MatchCardId, MatchId, TeamId
from bracket.utils.rate_limit import SlidingWindowLimiter

# Per link and client: reading (the page refreshes) and writing (results, check-ins, notices).
# Keys are only made for valid links; wrong tokens are limited per client, so guessing is slow.
score_link_reads = SlidingWindowLimiter(limit=300, window_seconds=60)
score_link_writes = SlidingWindowLimiter(limit=60, window_seconds=60)
invalid_link_attempts = SlidingWindowLimiter(limit=20, window_seconds=60)


async def score_link_dependency(token: str, request: Request) -> ScoreLink:
    client = request.client.host if request.client is not None else "unknown"
    link = await get_valid_score_link(token)
    if link is None:
        invalid_link_attempts.check(client)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This link is not valid (any more). Ask the organiser for a new one.",
        )
    limiter = score_link_reads if request.method == "GET" else score_link_writes
    limiter.check(f"{link.id}:{client}")
    if request.method != "GET":
        # Every change through a link (results, cards, check-in, notices): not when archived
        tournament = await sql_get_tournament(link.tournament_id)
        if tournament.status is TournamentStatus.ARCHIVED:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "The tournament is archived")
    return link


async def get_link_matches(
    link: ScoreLink,
) -> list[tuple[ScoreEntryMatch, MatchWithDetails | MatchWithDetailsDefinitive]]:
    """The scheduled matches the link gives access to, in order of time."""
    stages = await get_full_tournament_details(link.tournament_id)
    categories = {c.id: c for c in await get_all_categories_in_tournament(link.tournament_id)}
    courts = {c.id: c.name for c in await get_all_courts_in_tournament(link.tournament_id)}
    officials = await get_public_match_officials(link.tournament_id)
    cards = await get_cards(link.tournament_id)
    suspended = await get_suspended_players(link.tournament_id)

    result = []
    for stage in stages:
        for stage_item in stage.stage_items:
            for round_ in stage_item.rounds:
                for match in round_.matches:
                    if match.start_time is None or match.court_id is None:
                        continue
                    if link.court_id is not None and match.court_id != link.court_id:
                        continue
                    category = (
                        categories.get(stage.category_id) if stage.category_id is not None else None
                    )
                    team1_id, team1_name = team_of(match.stage_item_input1)
                    team2_id, team2_name = team_of(match.stage_item_input2)
                    checked_in = {
                        input_.team.id
                        for input_ in (match.stage_item_input1, match.stage_item_input2)
                        if isinstance(input_, StageItemInputFinal) and input_.team.checked_in
                    }
                    entry = ScoreEntryMatch(
                        id=match.id,
                        round_id=match.round_id,
                        court_id=match.court_id,
                        court_name=courts.get(match.court_id),
                        start_time=match.start_time,
                        duration_minutes=match.duration_minutes,
                        category_name=category.name if category is not None else None,
                        results_public=category.results_public if category is not None else True,
                        stage_item_name=stage_item.name,
                        team1_id=team1_id,
                        team1_name=team1_name,
                        team2_id=team2_id,
                        team2_name=team2_name,
                        team1_checked_in=team1_id in checked_in,
                        team2_checked_in=team2_id in checked_in,
                        score1=match.stage_item_input1_score,
                        score2=match.stage_item_input2_score,
                        penalties1=match.stage_item_input1_penalties,
                        penalties2=match.stage_item_input2_penalties,
                        played=match.played,
                        started_at=match.started_at,
                        result_type=match.result_type,
                        referee_name=next(
                            (
                                o.name
                                for o in officials
                                if o.match_id == match.id and o.role is MatchOfficialRole.REFEREE
                            ),
                            None,
                        ),
                        assistant_names=[
                            o.name
                            for o in officials
                            if o.match_id == match.id and o.role is MatchOfficialRole.ASSISTANT
                        ],
                        discipline_allowed=discipline_allowed(category),
                        cards=[card for card in cards if card.match_id == match.id],
                        suspended_players=suspended.get(match.id, []),
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
        walkover_goals=tournament.walkover_goals,
        matches=[entry for entry, _ in await get_link_matches(link)],
    )


async def get_enterable_match(
    link: ScoreLink, match_id: MatchId
) -> tuple[ScoreEntryMatch, MatchWithDetails | MatchWithDetailsDefinitive]:
    """A match of the link whose teams are known (archived: see `score_link_dependency`)."""
    found = next((pair for pair in await get_link_matches(link) if pair[0].id == match_id), None)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This match can't be entered with this link")
    if found[0].team1_id is None or found[0].team2_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "The teams of this match are not known yet"
        )
    return found


async def enter_result(link: ScoreLink, match_id: MatchId, body: ScoreEntryBody) -> None:
    _, match = await get_enterable_match(link, match_id)
    match_body = body.to_match_body(
        match.round_id, match.court_id, match.custom_duration_minutes, match.custom_margin_minutes
    )
    await save_match(link.tournament_id, match, match_body)


async def set_started(link: ScoreLink, match_id: MatchId, started: bool) -> None:
    _, match = await get_enterable_match(link, match_id)
    await sql_set_match_started(match.id, started)


async def enter_walkover(link: ScoreLink, match_id: MatchId, winner_team_id: TeamId) -> None:
    _, match = await get_enterable_match(link, match_id)
    await record_walkover(link.tournament_id, match, winner_team_id)


async def check_in_team(link: ScoreLink, team_id: TeamId, checked_in: bool) -> None:
    """At the pitch, only teams that play a match of the link can be checked in."""
    teams_of_link = {
        team
        for entry, _ in await get_link_matches(link)
        for team in (entry.team1_id, entry.team2_id)
        if team is not None
    }
    if team_id not in teams_of_link:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "This team can't be checked in with this link"
        )
    await set_team_flag(link.tournament_id, team_id, checked_in=checked_in)


async def enter_card(link: ScoreLink, match_id: MatchId, body: MatchCardBody) -> MatchCard:
    await get_enterable_match(link, match_id)
    await check_card(link.tournament_id, match_id, body)
    return await sql_create_card(link.tournament_id, match_id, body)


async def delete_card(link: ScoreLink, card_id: MatchCardId) -> None:
    """Only cards of the link's matches (e.g. a card entered by mistake)."""
    link_match_ids = {entry.id for entry, _ in await get_link_matches(link)}
    card = next((c for c in await get_cards(link.tournament_id) if c.id == card_id), None)
    if card is None or card.match_id not in link_match_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This card can't be changed with this link")
    await sql_delete_card(link.tournament_id, card_id)
