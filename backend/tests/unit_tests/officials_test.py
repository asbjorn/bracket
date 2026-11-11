from datetime import timedelta
from zoneinfo import ZoneInfo

from heliclockter import datetime_utc

from bracket.logic.officials import (
    MatchSlot,
    fee_summary,
    fees_csv,
    find_conflicts,
    matches_in_block,
)
from bracket.models.db.official import (
    CourtHost,
    MatchOfficial,
    MatchOfficialRole,
    Official,
    OfficialConflict,
    OfficialConflictKind,
)
from bracket.utils.id_types import CourtHostId, CourtId, MatchId, OfficialId, TournamentId

DAY = datetime_utc(2026, 6, 13, tzinfo=ZoneInfo("UTC"))


def at(hour: int, minute: int = 0, day: int = 0) -> datetime_utc:
    return DAY + timedelta(days=day, hours=hour, minutes=minute)


def official(id_: int, club: str | None = None, **changes: object) -> Official:
    return Official.model_validate(
        {
            "id": id_,
            "tournament_id": 1,
            "created": DAY,
            "name": f"Dommer {id_}",
            "club_name": club,
            "fee_per_match": 150,
            "fee_per_day": 200,
        }
        | changes
    )


def slot(id_: int, start: datetime_utc | None, court: int, *clubs: str) -> MatchSlot:
    end = start + timedelta(minutes=25) if start is not None else None
    return MatchSlot(MatchId(id_), start, end, CourtId(court), frozenset(clubs))


def assign(match_id: int, official_id: int, role: str = "REFEREE") -> MatchOfficial:
    return MatchOfficial(
        match_id=MatchId(match_id),
        official_id=OfficialId(official_id),
        role=MatchOfficialRole(role),
    )


SLOTS = {
    1: slot(1, at(9), 1, "brann", "lyn"),
    2: slot(2, at(9, 20), 2, "fana", "os"),  # Overlaps 1 (09:00-09:25)
    3: slot(3, at(9, 25), 1, "fana", "os"),  # Right after 1: fine
    4: slot(4, None, 1, "brann"),  # Not scheduled yet
    5: slot(5, at(10, 0, day=1), 1),
}
SLOTS_BY_ID = {MatchId(key): value for key, value in SLOTS.items()}


def test_double_booked() -> None:
    conflicts = find_conflicts(
        [official(1)], [assign(1, 1), assign(2, 1), assign(3, 1, "ASSISTANT")], SLOTS_BY_ID, []
    )
    assert conflicts == [
        OfficialConflict(
            official_id=OfficialId(1),
            kind=OfficialConflictKind.DOUBLE_BOOKED,
            match_id=MatchId(1),
            other_match_id=MatchId(2),
        ),
        # 2 (09:20-09:45) and 3 (09:25) overlap too
        OfficialConflict(
            official_id=OfficialId(1),
            kind=OfficialConflictKind.DOUBLE_BOOKED,
            match_id=MatchId(2),
            other_match_id=MatchId(3),
        ),
    ]


def test_back_to_back_and_unscheduled_are_fine() -> None:
    assert (
        find_conflicts([official(1)], [assign(1, 1), assign(3, 1), assign(4, 1)], SLOTS_BY_ID, [])
        == []
    )


def test_host_block_overlap() -> None:
    host = CourtHost(
        id=CourtHostId(7),
        tournament_id=TournamentId(1),
        official_id=OfficialId(1),
        court_id=CourtId(2),
        start_time=at(8),
        end_time=at(9, 10),
    )
    assert find_conflicts([official(1)], [assign(1, 1)], SLOTS_BY_ID, [host]) == [
        OfficialConflict(
            official_id=OfficialId(1),
            kind=OfficialConflictKind.DOUBLE_BOOKED,
            match_id=MatchId(1),
            court_host_id=CourtHostId(7),
        )
    ]


def test_own_club_and_inactive() -> None:
    conflicts = find_conflicts(
        [official(1, "Brann"), official(2, active=False)],
        [assign(1, 1), assign(4, 1, "ASSISTANT"), assign(3, 1), assign(5, 2)],
        SLOTS_BY_ID,
        [],
    )
    assert [(c.official_id, c.kind, c.match_id) for c in conflicts] == [
        (1, OfficialConflictKind.OWN_CLUB, 1),
        (1, OfficialConflictKind.OWN_CLUB, 4),
        (2, OfficialConflictKind.INACTIVE, None),
    ]


def test_fees() -> None:
    host = CourtHost(
        id=CourtHostId(7),
        tournament_id=TournamentId(1),
        official_id=OfficialId(2),
        court_id=CourtId(2),
        start_time=at(8),
        end_time=at(12),
    )
    fees = fee_summary(
        [official(1), official(2, fee_per_match=0)],
        [assign(1, 1), assign(3, 1), assign(5, 1), assign(4, 1)],
        SLOTS_BY_ID,
        [host],
    )
    # 4 matches, on 2 days (match 4 has no time yet)
    assert [(f.matches, f.days, f.host_days, f.total) for f in fees] == [
        (4, 2, 0, 4 * 150 + 2 * 200),
        (0, 1, 1, 200),
    ]
    csv = fees_csv([official(1), official(2, fee_per_match=0)], fees, "nb")
    assert csv.startswith('﻿"Navn";"Nivå";"Klubb";"Kamper"')
    assert csv.endswith('"Sum";"";"";"4";"";"";"";"1200"\r\n')


def test_days_count_in_norwegian_time() -> None:
    late = {MatchId(1): slot(1, at(22, 30), 1), MatchId(2): slot(2, at(23, 30), 1)}
    # 00:30 and 01:30 on the next day in Oslo (summer time)
    fees = fee_summary([official(1)], [assign(1, 1), assign(2, 1)], late, [])
    assert [fee.days for fee in fees] == [1]


def test_matches_in_block() -> None:
    assert matches_in_block(SLOTS_BY_ID, CourtId(1), at(9), at(9, 25)) == [1]
    assert matches_in_block(SLOTS_BY_ID, CourtId(1), at(9), at(10)) == [1, 3]
    assert matches_in_block(SLOTS_BY_ID, CourtId(2), at(10), at(11)) == []


def test_referee_age() -> None:
    slots = {
        MatchId(1): MatchSlot(MatchId(1), at(9), at(9, 25), CourtId(1), frozenset(), 10),
        MatchId(2): MatchSlot(MatchId(2), at(10), at(10, 25), CourtId(1), frozenset(), 14),
    }
    conflicts = find_conflicts(
        [official(1, age=12), official(2, age=13), official(3, age=40)],
        [assign(1, 1), assign(2, 2), assign(2, 3)],
        slots,
        [],
    )
    assert [(c.official_id, c.kind, c.match_id) for c in conflicts] == [
        (1, OfficialConflictKind.TOO_YOUNG, None),
        (2, OfficialConflictKind.YOUNGER_THAN_PLAYERS, 2),
    ]
    # Match hosts (kampverter) may be any age
    host = official(4, age=11, role="HOST")
    assert find_conflicts([host], [assign(1, 4)], slots, []) == []
