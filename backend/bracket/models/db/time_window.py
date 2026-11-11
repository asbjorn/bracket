from typing import Self

from heliclockter import datetime_utc
from pydantic import Field, model_validator

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import TimeWindowId, TournamentId

MAX_TIME_WINDOWS = 60


class TimeWindowBody(BaseModelORM):
    start_time: datetime_utc
    end_time: datetime_utc

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("A time window must end after it starts")
        return self


class TimeWindow(TimeWindowBody):
    id: TimeWindowId
    tournament_id: TournamentId


class TimeWindowsBody(BaseModelORM):
    """
    The periods in which matches can be played, e.g. 09:00-12:00 and 12:45-17:00 on both days.
    Replaces all existing time windows of the tournament.
    """

    time_windows: list[TimeWindowBody] = Field(max_length=MAX_TIME_WINDOWS)

    @model_validator(mode="after")
    def check_no_overlap(self) -> Self:
        windows = sorted(self.time_windows, key=lambda window: window.start_time)
        for previous, current in zip(windows, windows[1:], strict=False):
            if current.start_time < previous.end_time:
                raise ValueError("Time windows can't overlap")
        return self
