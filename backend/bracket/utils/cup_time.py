"""
The cup is played in Norway: "days" (per-day limits, fees per day, dates in texts) are calendar
days in Norwegian time, while everything is stored in UTC.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from heliclockter import datetime_utc

CUP_TIMEZONE = ZoneInfo("Europe/Oslo")


def cup_day(moment: datetime) -> date:
    return moment.astimezone(CUP_TIMEZONE).date()


def next_cup_midnight(moment: datetime) -> datetime_utc:
    """The start of the next day in Norwegian time (correct across daylight saving changes)."""
    local_midnight = datetime.combine(cup_day(moment) + timedelta(days=1), time(), CUP_TIMEZONE)
    return datetime_utc.fromisoformat(local_midnight.astimezone(ZoneInfo("UTC")).isoformat())
