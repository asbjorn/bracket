from datetime import timedelta
from zoneinfo import ZoneInfo

from heliclockter import datetime_utc

from bracket.logic.ical import CalendarEvent, build_calendar, escape_text, fold_line

NOW = datetime_utc(2026, 6, 13, 6, 0, tzinfo=ZoneInfo("UTC"))


def test_escape_text() -> None:
    assert escape_text("a,b;c\\d\ne") == r"a\,b\;c\\d\ne"


def test_fold_line() -> None:
    line = "DESCRIPTION:" + "Åsane–Nest-Sotra, " * 10
    folded = fold_line(line)
    parts = folded.split("\r\n")
    assert len(parts) > 1
    assert all(len(part.encode()) <= 75 for part in parts)
    assert all(part.startswith(" ") for part in parts[1:])
    # Unfolding gives the original line, and no character is split
    assert "".join([parts[0]] + [part[1:] for part in parts[1:]]) == line
    assert fold_line("SHORT:line") == "SHORT:line"


def test_build_calendar() -> None:
    event = CalendarEvent(
        uid="match-1-tournament-2@bracket",
        start=NOW + timedelta(hours=3),
        end=NOW + timedelta(hours=3, minutes=12),
        summary="Brann – Lyn",
        location="Bane 1, kunstgress",
        description="G10 · Gruppe A",
    )
    calendar = build_calendar("Brann – Vårcup", [event], NOW)
    assert calendar.endswith("END:VCALENDAR\r\n")
    assert "\n" not in calendar.replace("\r\n", "")
    lines = calendar.split("\r\n")
    assert lines[0] == "BEGIN:VCALENDAR"
    assert "VERSION:2.0" in lines
    assert "UID:match-1-tournament-2@bracket" in lines
    assert "DTSTAMP:20260613T060000Z" in lines
    assert "DTSTART:20260613T090000Z" in lines
    assert "DTEND:20260613T091200Z" in lines
    assert r"LOCATION:Bane 1\, kunstgress" in lines
    assert lines.count("BEGIN:VEVENT") == lines.count("END:VEVENT") == 1
