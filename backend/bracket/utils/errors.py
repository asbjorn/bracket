from collections.abc import Iterator
from contextlib import contextmanager
from enum import auto

import asyncpg  # type: ignore[import-untyped]
from fastapi import HTTPException
from starlette import status

from bracket.utils.logging import logger
from bracket.utils.types import EnumAutoStr


class UniqueIndex(EnumAutoStr):
    categories_tournament_id_name_key = auto()
    ix_tournaments_dashboard_endpoint = auto()
    ix_users_email = auto()
    ix_match_officials_one_referee = auto()
    ix_participating_clubs_tournament_id_lower_name = auto()
    team_conflicts_team1_id_team2_id_key = auto()
    match_officials_match_id_official_id_key = auto()
    notifications_sent_tournament_id_dedupe_key_key = auto()
    score_links_token_hash_key = auto()
    stage_item_inputs_stage_item_id_team_id_key = auto()
    stage_item_inputs_stage_item_id_winner_from_stage_item_id_w_key = auto()


class ForeignKey(EnumAutoStr):
    stages_category_id_fkey = auto()
    teams_category_id_fkey = auto()
    courts_tournament_id_fkey = auto()
    matches_stage_item_input1_id_fkey = auto()
    matches_stage_item_input2_id_fkey = auto()
    players_tournament_id_fkey = auto()
    stage_item_inputs_team_id_fkey = auto()
    stages_tournament_id_fkey = auto()
    teams_tournament_id_fkey = auto()
    tournaments_club_id_fkey = auto()
    rankings_tournament_id_fkey = auto()
    stage_item_inputs_best_from_stage_id_fkey = auto()


unique_index_violation_error_lookup = {
    UniqueIndex.categories_tournament_id_name_key: "A class with this name already exists",
    UniqueIndex.ix_tournaments_dashboard_endpoint: "This dashboard link is already taken",
    UniqueIndex.ix_users_email: "This email is already taken",
    UniqueIndex.ix_match_officials_one_referee: "This match already has a referee",
    UniqueIndex.team_conflicts_team1_id_team2_id_key: "These teams are already linked",
    UniqueIndex.ix_participating_clubs_tournament_id_lower_name: (
        "A club with this name already takes part in this cup"
    ),
    UniqueIndex.match_officials_match_id_official_id_key: (
        "An official can only have one role in a match"
    ),
    # Queued with ON CONFLICT DO NOTHING, so this doesn't reach the user
    UniqueIndex.notifications_sent_tournament_id_dedupe_key_key: "This email was already sent",
    # A random 256-bit token: practically never happens
    UniqueIndex.score_links_token_hash_key: "Could not create a unique link, try again",
    UniqueIndex.stage_item_inputs_stage_item_id_team_id_key: (
        "This team is already assigned to another stage item"
    ),
    UniqueIndex.stage_item_inputs_stage_item_id_winner_from_stage_item_id_w_key: (
        "This stage item winner is already assigned to another stage item"
    ),
}


foreign_key_violation_error_lookup = {
    ForeignKey.stages_category_id_fkey: "This class still has stages, delete those first",
    ForeignKey.teams_category_id_fkey: (
        "This class still has teams, move them to another class or delete them first"
    ),
    ForeignKey.courts_tournament_id_fkey: "This tournament still has courts, delete those first",
    ForeignKey.matches_stage_item_input1_id_fkey: "This team is still part of matches",
    ForeignKey.matches_stage_item_input2_id_fkey: "This team is still part of matches",
    ForeignKey.players_tournament_id_fkey: "This tournament still has players, delete those first",
    ForeignKey.stage_item_inputs_team_id_fkey: "Invalid team as input to this stage item",
    ForeignKey.stages_tournament_id_fkey: "This tournament still has stages, delete those first",
    ForeignKey.teams_tournament_id_fkey: "This tournament still has teams, delete those first",
    ForeignKey.tournaments_club_id_fkey: "This club still has tournaments, delete those first",
    ForeignKey.rankings_tournament_id_fkey: (
        "This tournament still has rankings, delete those first"
    ),
    ForeignKey.stage_item_inputs_best_from_stage_id_fkey: (
        "A later stage takes its best placed teams from this stage, delete that one first"
    ),
}

# For a reference the endpoint didn't expect: still a clear answer instead of a server error
GENERIC_FOREIGN_KEY_VIOLATION = "This is still in use elsewhere, so it can't be changed or deleted"


@contextmanager
def check_unique_constraint_violation(expected_violations: set[UniqueIndex]) -> Iterator[None]:
    try:
        yield
    except asyncpg.exceptions.UniqueViolationError as exc:
        constraint_name = exc.as_dict()["constraint_name"]
        assert constraint_name, "UniqueViolationError occurred but no constraint_name defined"
        assert constraint_name in UniqueIndex.values(), "Unknown UniqueViolationError occurred"
        constraint = UniqueIndex(constraint_name)

        if (
            constraint not in unique_index_violation_error_lookup
            or constraint not in expected_violations
        ):
            raise exc

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=unique_index_violation_error_lookup[constraint],
        ) from exc


@contextmanager
def check_foreign_key_violation(expected_violations: set[ForeignKey]) -> Iterator[None]:
    try:
        yield
    except asyncpg.exceptions.ForeignKeyViolationError as exc:
        constraint_name = exc.as_dict().get("constraint_name")
        constraint = ForeignKey(constraint_name) if constraint_name in ForeignKey.values() else None
        if (
            constraint is None
            or constraint not in foreign_key_violation_error_lookup
            or constraint not in expected_violations
        ):
            logger.warning(f"Unexpected foreign key violation: {constraint_name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=GENERIC_FOREIGN_KEY_VIOLATION
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=foreign_key_violation_error_lookup[constraint],
        ) from exc
