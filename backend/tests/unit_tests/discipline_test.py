from datetime import timedelta
from zoneinfo import ZoneInfo

from heliclockter import datetime_utc

from bracket.logic.discipline import (
    TeamMatch,
    compute_suspensions,
    discipline_allowed,
    schedule_order,
    suspended_in_match,
)
from bracket.models.db.category import Category
from bracket.models.db.discipline import JuryDecision, MatchCard, Suspension, SuspensionReason
from bracket.utils.id_types import MatchId, TeamId

DAY = datetime_utc(2026, 6, 13, tzinfo=ZoneInfo("UTC"))
BRANN, LYN = TeamId(1), TeamId(2)
# Brann plays 10, 11, 12, 13 (in that order by time; ids out of order on purpose)
SCHEDULE = {
    BRANN: [
        TeamMatch(MatchId(12), DAY + timedelta(hours=11)),
        TeamMatch(MatchId(10), DAY + timedelta(hours=9)),
        TeamMatch(MatchId(13), None),
        TeamMatch(MatchId(11), DAY + timedelta(hours=10)),
    ],
    LYN: [TeamMatch(MatchId(10), DAY + timedelta(hours=9))],
}


def only(suspensions: list[Suspension]) -> Suspension:
    assert len(suspensions) == 1
    return suspensions[0]


def card(id_: int, match: int, player: str, type_: str, team: TeamId = BRANN) -> MatchCard:
    return MatchCard.model_validate(
        {
            "id": id_,
            "tournament_id": 1,
            "match_id": match,
            "created": DAY,
            "team_id": team,
            "player_name": player,
            "card_type": type_,
        }
    )


def decision(card_id: int, change: int) -> JuryDecision:
    return JuryDecision.model_validate(
        {
            "id": card_id,
            "tournament_id": 1,
            "decided_at": DAY,
            "text": "Juryen",
            "card_id": card_id,
            "suspension_change": change,
        }
    )


def test_schedule_order() -> None:
    assert schedule_order(SCHEDULE[BRANN]) == [10, 11, 12, 13]


def test_red_card_suspends_next_matches() -> None:
    one = only(compute_suspensions([card(1, 10, "Ola", "RED")], SCHEDULE, 1, None, []))
    assert (one.reason, one.match_ids, one.matches) == (SuspensionReason.RED_CARD, [11], 1)

    two = only(compute_suspensions([card(1, 11, "Ola", "YELLOW_RED")], SCHEDULE, 2, None, []))
    assert two.match_ids == [12, 13]

    # The team's last match: nothing left to sit out (but the suspension stays on record)
    last = only(compute_suspensions([card(1, 13, "Ola", "RED")], SCHEDULE, 1, None, []))
    assert (last.match_ids, last.matches) == ([], 1)

    assert not compute_suspensions([card(1, 10, "Ola", "RED")], SCHEDULE, 0, None, [])


def test_yellow_cards() -> None:
    cards = [
        card(1, 10, "Ola", "YELLOW"),
        card(2, 11, " ola ", "YELLOW"),  # The same player, written differently
        card(3, 11, "Per", "YELLOW"),
        card(4, 10, "Ola", "YELLOW", team=LYN),  # Another team's Ola
    ]
    assert not compute_suspensions(cards, SCHEDULE, 1, None, [])
    ola = only(compute_suspensions(cards, SCHEDULE, 1, 2, []))
    assert (ola.team_id, ola.card_id, ola.reason, ola.match_ids) == (
        BRANN,
        2,
        SuspensionReason.YELLOW_CARDS,
        [12],
    )


def test_jury_changes_suspensions() -> None:
    cards = [card(1, 10, "Ola", "RED"), card(2, 10, "Per", "YELLOW")]
    suspensions = compute_suspensions(cards, SCHEDULE, 1, None, [decision(1, 1), decision(2, 1)])
    assert [(s.player_name, s.match_ids) for s in suspensions] == [("Ola", [11, 12]), ("Per", [11])]
    # The jury lifts the red card's suspension
    assert not compute_suspensions(cards, SCHEDULE, 1, None, [decision(1, -1)])
    assert [s.player_name for s in suspended_in_match(suspensions, MatchId(12))] == ["Ola"]


def category(age: int | None, public: bool) -> Category:
    return Category.model_validate(
        {
            "id": 1,
            "tournament_id": 1,
            "name": "K",
            "created": DAY,
            "age": age,
            "results_public": public,
        }
    )


def test_discipline_allowed() -> None:
    assert discipline_allowed(None)
    assert discipline_allowed(category(None, True))
    assert discipline_allowed(category(13, True))
    assert not discipline_allowed(category(12, True))
    assert not discipline_allowed(category(16, False))
