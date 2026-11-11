"""
Discipline for youth football (13 years and older): cards and automatic suspensions.

- A red card (or a second yellow in a match) suspends the player for the team's next
  `suspension_matches_per_red` matches.
- Optionally, every `yellow_cards_for_suspension`-th yellow card of a player suspends them for
  the team's next match.
- The jury can change the suspension of a card: its decisions add or remove matches.

"Next matches" follow the team's schedule (time, then id). Players are identified per team by
their name (case and spaces ignored), since cards are often written down by hand.

Children's football (12 and younger) and classes with hidden results have no discipline.
"""

from collections import defaultdict
from dataclasses import dataclass

from heliclockter import datetime_utc

from bracket.models.db.category import YOUTH_FOOTBALL_MIN_AGE, Category
from bracket.models.db.discipline import (
    CardType,
    JuryDecision,
    MatchCard,
    Suspension,
    SuspensionReason,
)
from bracket.utils.id_types import MatchCardId, MatchId, TeamId


def discipline_allowed(category: Category | None) -> bool:
    if category is None:
        return True
    youth = category.age is None or category.age >= YOUTH_FOOTBALL_MIN_AGE
    return youth and category.results_public


@dataclass(frozen=True)
class TeamMatch:
    match_id: MatchId
    start: datetime_utc | None


def schedule_order(matches: list[TeamMatch]) -> list[MatchId]:
    """Scheduled matches by time, matches without a time last."""
    return [
        match.match_id
        for match in sorted(
            matches, key=lambda m: (m.start is None, m.start or datetime_utc.min, m.match_id)
        )
    ]


def player_key(card: MatchCard) -> tuple[TeamId, str]:
    return card.team_id, " ".join(card.player_name.casefold().split())


def matches_after(order: list[MatchId], match_id: MatchId, count: int) -> list[MatchId]:
    if count <= 0 or match_id not in order:
        return []
    index = order.index(match_id)
    return order[index + 1 : index + 1 + count]


def suspension_changes(decisions: list[JuryDecision]) -> dict[MatchCardId, int]:
    changes: dict[MatchCardId, int] = defaultdict(int)
    for decision in decisions:
        if decision.card_id is not None:
            changes[decision.card_id] += decision.suspension_change
    return changes


def compute_suspensions(
    cards: list[MatchCard],
    team_matches: dict[TeamId, list[TeamMatch]],
    suspension_matches_per_red: int,
    yellow_cards_for_suspension: int | None,
    decisions: list[JuryDecision],
) -> list[Suspension]:
    orders = {team_id: schedule_order(matches) for team_id, matches in team_matches.items()}
    changes = suspension_changes(decisions)

    def position(card: MatchCard) -> tuple[int, int]:
        order = orders.get(card.team_id, [])
        index = order.index(card.match_id) if card.match_id in order else len(order)
        return index, card.id

    def suspension(card: MatchCard, reason: SuspensionReason, count: int) -> Suspension | None:
        count = max(0, count + changes.get(card.id, 0))
        if count < 1:
            return None
        match_ids = matches_after(orders.get(card.team_id, []), card.match_id, count)
        return Suspension(
            team_id=card.team_id,
            player_name=card.player_name,
            reason=reason,
            card_id=card.id,
            match_ids=match_ids,
            matches=count,
        )

    suspensions = []
    yellows: dict[tuple[TeamId, str], int] = defaultdict(int)
    for card in sorted(cards, key=position):
        if card.card_type in {CardType.RED, CardType.YELLOW_RED}:
            result = suspension(card, SuspensionReason.RED_CARD, suspension_matches_per_red)
        else:
            # Without a threshold yellows only suspend when the jury decides so
            matches = 0
            if yellow_cards_for_suspension is not None:
                yellows[player_key(card)] += 1
                if yellows[player_key(card)] % yellow_cards_for_suspension == 0:
                    matches = 1
            result = suspension(card, SuspensionReason.YELLOW_CARDS, matches)
        if result is not None:
            suspensions.append(result)
    return suspensions


def suspended_in_match(suspensions: list[Suspension], match_id: MatchId) -> list[Suspension]:
    return [s for s in suspensions if match_id in s.match_ids]
