from enum import StrEnum
from typing import Annotated

from heliclockter import datetime_utc
from pydantic import BaseModel, StringConstraints

MAX_RULES_LENGTH = 20_000


class AnnouncementLevel(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"


class Announcement(BaseModel):
    """A banner on all public pages, e.g. "Lightning: all matches paused until 14:00"."""

    text: Annotated[str, StringConstraints(min_length=1, max_length=500, strip_whitespace=True)]
    level: AnnouncementLevel = AnnouncementLevel.INFO
    # Hidden after this moment; `None`: until removed
    until: datetime_utc | None = None


class AnnouncementBody(BaseModel):
    """`announcement: None` removes the announcement."""

    announcement: Announcement | None


class PublicDelay(BaseModel):
    """A delay reported from a pitch; the public only sees the court and the minutes."""

    court_name: str | None
    delay_minutes: int
    created: datetime_utc


class PublicNotices(BaseModel):
    announcement: Announcement | None
    delays: list[PublicDelay]


class Rules(BaseModel):
    text: Annotated[str, StringConstraints(max_length=MAX_RULES_LENGTH)]
