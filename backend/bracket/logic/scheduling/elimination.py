"""
Single elimination (knockout) brackets for any number of teams.

When the number of teams is not a power of two, some teams get a bye: they skip the first round
and start in the second round. Teams fill the bracket from top to bottom in slot order, and the
byes follow standard seeding (see `get_seed_per_slot`), so they are spread over the bracket.
"""

import math
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException
from starlette import status

from bracket.models.db.match import Match, MatchCreateBody
from bracket.models.db.tournament import Tournament
from bracket.models.db.util import StageItemWithRounds
from bracket.sql.matches import sql_create_match
from bracket.sql.rounds import get_rounds_for_stage_item
from bracket.sql.tournaments import sql_get_tournament
from bracket.utils.id_types import TournamentId

MIN_TEAMS_THIRD_PLACE_MATCH = 4


@dataclass(frozen=True)
class FromInput:
    """The team in this slot (index in slot order) of the stage item."""

    slot_index: int


@dataclass(frozen=True)
class FromMatch:
    """The winner or loser of a match planned earlier: `round_index`, `match_index`."""

    outcome: Literal["winner", "loser"]
    round_index: int
    match_index: int


Source = FromInput | FromMatch
PlannedMatch = tuple[Source, Source]


def standard_seed_order(bracket_size: int) -> list[int]:
    """
    The seeds (1 = best) at each position of a bracket, such that seed 1 plays the lowest seed,
    and the best seeds can only meet as late as possible. E.g. for 8: [1, 8, 4, 5, 2, 7, 3, 6].
    """
    order = [1]
    while len(order) < bracket_size:
        size = len(order) * 2
        order = [seed for previous in order for seed in (previous, size + 1 - previous)]
    return order


def get_bracket_size(team_count: int) -> int:
    return 1 << math.ceil(math.log2(team_count))


def get_bye_pairs(team_count: int) -> set[int]:
    """
    The pairs of the first round (of a bracket rounded up to a power of two) where a team gets
    a bye: following standard seeding, the best seeds get a bye, spread over the bracket.
    """
    order = standard_seed_order(get_bracket_size(team_count))
    return {
        pair for pair in range(len(order) // 2) if max(order[2 * pair : 2 * pair + 2]) > team_count
    }


def get_seed_per_slot(team_count: int) -> list[int]:
    """
    Which seed to put in each slot, so that the bracket follows standard seeding: seed 1 plays
    the lowest seed (or has a bye), etc. Slots fill the bracket from top to bottom.
    """
    return [
        seed for seed in standard_seed_order(get_bracket_size(team_count)) if seed <= team_count
    ]


def plan_single_elimination(
    team_count: int, *, third_place_match: bool = False
) -> list[list[PlannedMatch]]:
    """
    Plans the matches per round. A third place match is added to the last round, between the
    losers of the semifinals.
    """
    if team_count < 2:
        return []
    if third_place_match and team_count < MIN_TEAMS_THIRD_PLACE_MATCH:
        raise ValueError("A third place match needs at least 4 teams")

    bye_pairs = get_bye_pairs(team_count)
    pair_count = get_bracket_size(team_count) // 2

    first_round: list[PlannedMatch] = []
    positions: list[Source] = []
    next_slot = 0
    for pair in range(pair_count):
        if pair in bye_pairs:
            positions.append(FromInput(next_slot))
            next_slot += 1
        else:
            first_round.append((FromInput(next_slot), FromInput(next_slot + 1)))
            positions.append(FromMatch("winner", 0, len(first_round) - 1))
            next_slot += 2
    assert next_slot == team_count

    rounds = [first_round]
    while len(positions) > 1:
        round_index = len(rounds)
        matches = [(positions[i], positions[i + 1]) for i in range(0, len(positions), 2)]
        positions = [FromMatch("winner", round_index, i) for i in range(len(matches))]
        rounds.append(matches)

    if third_place_match:
        semifinal_round = len(rounds) - 2
        rounds[-1].append(
            (FromMatch("loser", semifinal_round, 0), FromMatch("loser", semifinal_round, 1))
        )
    return rounds


def to_match_create_body(
    planned: PlannedMatch,
    round_id: int,
    stage_item: StageItemWithRounds,
    created_matches: list[list[Match]],
    tournament: Tournament,
) -> MatchCreateBody:
    inputs = sorted(stage_item.inputs, key=lambda input_: input_.slot)
    values: dict[str, object] = {}
    for index, source in enumerate(planned, start=1):
        match source:
            case FromInput(slot_index):
                values[f"stage_item_input{index}_id"] = inputs[slot_index].id
            case FromMatch(outcome, round_index, match_index):
                match_id = created_matches[round_index][match_index].id
                values[f"stage_item_input{index}_{outcome}_from_match_id"] = match_id

    return MatchCreateBody.model_validate(
        {
            "round_id": round_id,
            "court_id": None,
            "duration_minutes": tournament.duration_minutes,
            "margin_minutes": tournament.margin_minutes,
            "custom_duration_minutes": None,
            "custom_margin_minutes": None,
            **values,
        }
    )


async def build_single_elimination_stage_item(
    tournament_id: TournamentId,
    stage_item: StageItemWithRounds,
    *,
    third_place_match: bool = False,
) -> None:
    # Rounds are created in order, the database doesn't guarantee their order in results
    rounds = sorted(
        await get_rounds_for_stage_item(tournament_id, stage_item.id), key=lambda r: r.id
    )
    tournament = await sql_get_tournament(tournament_id)
    plan = plan_single_elimination(stage_item.team_count, third_place_match=third_place_match)
    assert len(rounds) == len(plan), f"Expected {len(plan)} rounds, got {len(rounds)}"

    created_matches: list[list[Match]] = []
    for round_, planned_matches in zip(rounds, plan, strict=True):
        created_matches.append(
            [
                await sql_create_match(
                    to_match_create_body(
                        planned, round_.id, stage_item, created_matches, tournament
                    )
                )
                for planned in planned_matches
            ]
        )


def get_number_of_rounds_to_create_single_elimination(team_count: int) -> int:
    if team_count < 1:
        return 0
    if team_count == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A knockout bracket needs at least 2 teams",
        )
    return math.ceil(math.log2(team_count))
