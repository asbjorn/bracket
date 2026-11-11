"""
iCalendar (RFC 5545) output: a team's matches as a feed that calendar apps can subscribe to.
"""

from dataclasses import dataclass

from heliclockter import datetime_utc

MAX_LINE_OCTETS = 75


@dataclass(frozen=True)
class CalendarEvent:
    uid: str
    start: datetime_utc
    end: datetime_utc
    summary: str
    location: str | None = None
    description: str | None = None


def escape_text(value: str) -> str:
    """TEXT values: backslash, semicolon, comma and newlines are escaped (RFC 5545 3.3.11)."""
    return (
        value.replace("\\", r"\\")
        .replace(";", r"\;")
        .replace(",", r"\,")
        .replace("\r\n", r"\n")
        .replace("\n", r"\n")
        .replace("\r", r"\n")
    )


def fold_line(line: str) -> str:
    """Lines longer than 75 octets continue on the next line after CRLF + space (3.1)."""
    parts: list[str] = []
    current = ""
    current_octets = 0
    for char in line:
        octets = len(char.encode())
        # Continuation lines start with a space, which counts too
        limit = MAX_LINE_OCTETS if not parts else MAX_LINE_OCTETS - 1
        if current_octets + octets > limit:
            parts.append(current)
            current, current_octets = "", 0
        current += char
        current_octets += octets
    parts.append(current)
    return "\r\n ".join(parts)


def format_time(moment: datetime_utc) -> str:
    return moment.strftime("%Y%m%dT%H%M%SZ")


def build_calendar(name: str, events: list[CalendarEvent], now: datetime_utc) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Bracket//Cup schedule//NB",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_text(name)}",
    ]
    for event in events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{event.uid}",
            f"DTSTAMP:{format_time(now)}",
            f"DTSTART:{format_time(event.start)}",
            f"DTEND:{format_time(event.end)}",
            f"SUMMARY:{escape_text(event.summary)}",
        ]
        if event.location:
            lines.append(f"LOCATION:{escape_text(event.location)}")
        if event.description:
            lines.append(f"DESCRIPTION:{escape_text(event.description)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "".join(f"{fold_line(line)}\r\n" for line in lines)
