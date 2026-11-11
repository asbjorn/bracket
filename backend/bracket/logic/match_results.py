from bracket.logic.planning.matches import (
    get_scheduled_matches,
    get_windows,
    reorder_matches_for_court,
)
from bracket.logic.ranking.calculation import recalculate_ranking_for_stage_item
from bracket.logic.ranking.elimination import update_inputs_in_subsequent_elimination_rounds
from bracket.models.db.match import Match, MatchBody
from bracket.models.db.stage_item import StageType
from bracket.sql.matches import sql_apply_default_timing, sql_update_match
from bracket.sql.rounds import get_round_by_id
from bracket.sql.stage_items import get_stage_item
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.tournaments import sql_get_tournament
from bracket.utils.id_types import TournamentId


async def save_match(tournament_id: TournamentId, match: Match, match_body: MatchBody) -> None:
    """
    Saves a match (result, court, timing) and everything that follows from it: rankings,
    the teams of later knockout rounds and, for a new duration, the times on its court.
    `match` must belong to the tournament.
    """
    tournament = await sql_get_tournament(tournament_id)

    await sql_update_match(
        match.id, match_body, tournament, played=match_body.is_played(match.played)
    )
    # The class of the match may have its own duration and margin
    await sql_apply_default_timing(tournament_id)

    round_ = await get_round_by_id(tournament_id, match.round_id)
    stage_item = await get_stage_item(tournament_id, round_.stage_item_id)
    await recalculate_ranking_for_stage_item(tournament_id, stage_item)

    timing_changed = (
        match_body.custom_duration_minutes != match.custom_duration_minutes
        or match_body.custom_margin_minutes != match.custom_margin_minutes
    )
    # An unscheduled match has no court whose times would change
    if timing_changed and match.court_id is not None:
        tournament = await sql_get_tournament(tournament_id)
        scheduled_matches = get_scheduled_matches(await get_full_tournament_details(tournament_id))
        await reorder_matches_for_court(
            tournament,
            scheduled_matches,
            match.court_id,
            await get_windows(tournament_id),
        )

    if stage_item.type == StageType.SINGLE_ELIMINATION:
        await update_inputs_in_subsequent_elimination_rounds(round_.id, stage_item, {match.id})
