"""
Referees and match hosts: conflict checks and the fee summary. Pure functions on plain data, so
the rules are easy to test; `sql/officials.py` and the routes load and save.

Conflicts (warnings for the organiser, nothing is blocked):
- DOUBLE_BOOKED: an official has two matches, or a match and a host block, at the same time
  (a match lasts its duration plus margin).
- OWN_CLUB: a referee of a match where a team of their own club plays.
- INACTIVE: an official marked as not active still has matches.

An official that also plays in a team can't be detected: officials aren't linked to players.
"""

from dataclasses import dataclass
from datetime import date
from itertools import combinations
from zoneinfo import ZoneInfo

from heliclockter import datetime_utc

from bracket.logic.scheduling.group_draw import club_of
from bracket.models.db.official import (
    CourtHost,
    MatchOfficial,
    Official,
    OfficialConflict,
    OfficialConflictKind,
    OfficialFee,
)
from bracket.utils.csv_export import to_csv
from bracket.utils.id_types import CourtHostId, CourtId, MatchId, OfficialId

# Days of a cup (for fees per day) are counted in Norwegian time
CUP_TIMEZONE = ZoneInfo("Europe/Oslo")


@dataclass(frozen=True)
class MatchSlot:
    id: MatchId
    start: datetime_utc | None
    end: datetime_utc | None  # Including the margin
    court_id: CourtId | None
    clubs: frozenset[str]  # Clubs of the known teams


@dataclass(frozen=True)
class Busy:
    start: datetime_utc
    end: datetime_utc
    match_id: MatchId | None = None
    court_host_id: CourtHostId | None = None


def busy_periods(
    official_id: OfficialId,
    assignments: list[MatchOfficial],
    slots: dict[MatchId, MatchSlot],
    hosts: list[CourtHost],
) -> list[Busy]:
    periods = [
        Busy(slot.start, slot.end, match_id=slot.id)
        for assignment in assignments
        if assignment.official_id == official_id
        and (slot := slots.get(assignment.match_id)) is not None
        and slot.start is not None
        and slot.end is not None
    ]
    periods += [
        Busy(host.start_time, host.end_time, court_host_id=host.id)
        for host in hosts
        if host.official_id == official_id
    ]
    return sorted(periods, key=lambda busy: (busy.start, busy.end))


def double_bookings(official_id: OfficialId, periods: list[Busy]) -> list[OfficialConflict]:
    conflicts = []
    for first, second in combinations(periods, 2):
        if second.start < first.end and first.start < second.end:
            match_id = first.match_id if first.match_id is not None else second.match_id
            other_match_id = second.match_id if first.match_id is not None else None
            court_host_id = (
                first.court_host_id if first.court_host_id is not None else second.court_host_id
            )
            conflicts.append(
                OfficialConflict(
                    official_id=official_id,
                    kind=OfficialConflictKind.DOUBLE_BOOKED,
                    match_id=match_id,
                    other_match_id=other_match_id,
                    court_host_id=court_host_id,
                )
            )
    return conflicts


def find_conflicts(
    officials: list[Official],
    assignments: list[MatchOfficial],
    slots: dict[MatchId, MatchSlot],
    hosts: list[CourtHost],
) -> list[OfficialConflict]:
    conflicts: list[OfficialConflict] = []
    for official in officials:
        own = [a for a in assignments if a.official_id == official.id]
        conflicts += double_bookings(official.id, busy_periods(official.id, own, slots, hosts))
        if official.club_name:
            club = club_of(official.club_name, official.club_name)
            conflicts += [
                OfficialConflict(
                    official_id=official.id,
                    kind=OfficialConflictKind.OWN_CLUB,
                    match_id=assignment.match_id,
                )
                for assignment in own
                if (slot := slots.get(assignment.match_id)) is not None and club in slot.clubs
            ]
        if not official.active and (own or any(h.official_id == official.id for h in hosts)):
            conflicts.append(
                OfficialConflict(official_id=official.id, kind=OfficialConflictKind.INACTIVE)
            )
    return conflicts


def local_day(moment: datetime_utc) -> date:
    return moment.astimezone(CUP_TIMEZONE).date()


def fee_summary(
    officials: list[Official],
    assignments: list[MatchOfficial],
    slots: dict[MatchId, MatchSlot],
    hosts: list[CourtHost],
) -> list[OfficialFee]:
    """Per official: fee per match × matches + fee per day × days with a match or host block."""
    fees = []
    for official in officials:
        match_ids = {a.match_id for a in assignments if a.official_id == official.id}
        match_days = {
            local_day(start)
            for match_id in match_ids
            if (slot := slots.get(match_id)) is not None and (start := slot.start) is not None
        }
        host_days = {local_day(h.start_time) for h in hosts if h.official_id == official.id}
        days = len(match_days | host_days)
        fees.append(
            OfficialFee(
                official_id=official.id,
                name=official.name,
                matches=len(match_ids),
                days=days,
                host_days=len(host_days),
                total=official.fee_per_match * len(match_ids) + official.fee_per_day * days,
            )
        )
    return fees


def matches_in_block(
    slots: dict[MatchId, MatchSlot],
    court_id: CourtId,
    start: datetime_utc,
    end: datetime_utc,
) -> list[MatchId]:
    """The matches on the court that start in [start, end)."""
    return sorted(
        slot.id
        for slot in slots.values()
        if slot.court_id == court_id and slot.start is not None and start <= slot.start < end
    )


FEE_CSV_HEADERS = {
    "en": ["Name", "Level", "Club", "Matches", "Days", "Fee per match", "Fee per day", "Total"],
    "nb": ["Navn", "Nivå", "Klubb", "Kamper", "Dager", "Per kamp", "Per dag", "Sum"],
}


def fees_csv(officials: list[Official], fees: list[OfficialFee], language: str) -> str:
    """The fee summary for a spreadsheet (see `utils/csv_export`), with a total row."""
    header = FEE_CSV_HEADERS.get(language, FEE_CSV_HEADERS["en"])
    by_id = {official.id: official for official in officials}
    rows: list[list[object]] = [
        [
            fee.name,
            by_id[fee.official_id].level,
            by_id[fee.official_id].club_name,
            fee.matches,
            fee.days,
            by_id[fee.official_id].fee_per_match,
            by_id[fee.official_id].fee_per_day,
            fee.total,
        ]
        for fee in fees
    ]
    rows.append(
        [header[-1], "", "", sum(f.matches for f in fees), "", "", "", sum(f.total for f in fees)]
    )
    return to_csv(header, rows)
