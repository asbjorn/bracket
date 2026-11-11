from decimal import Decimal
from enum import auto
from typing import Self

from heliclockter import datetime_utc, timedelta
from pydantic import BaseModel, Field, model_validator

from bracket.models.db.court import Court
from bracket.models.db.shared import BaseModelORM
from bracket.models.db.stage_item_inputs import StageItemInput
from bracket.utils.id_types import CourtId, MatchId, RoundId, StageItemInputId
from bracket.utils.types import EnumAutoStr, assert_some


class MatchResultType(EnumAutoStr):
    NORMAL = auto()
    # The score includes the goals of extra time
    EXTRA_TIME = auto()
    # The score is equal (after normal or extra time), the penalty shootout decides
    PENALTIES = auto()
    # A team didn't show up, the score is set by the tournament rules (e.g. 3-0)
    WALKOVER = auto()


class MatchBaseInsertable(BaseModelORM):
    created: datetime_utc
    start_time: datetime_utc | None = None
    duration_minutes: int
    margin_minutes: int
    custom_duration_minutes: int | None = None
    custom_margin_minutes: int | None = None
    position_in_schedule: int | None = None
    round_id: RoundId
    stage_item_input1_score: int
    stage_item_input2_score: int
    court_id: CourtId | None = None
    stage_item_input1_conflict: bool
    stage_item_input2_conflict: bool
    # Whether the match has been played. Only played matches count in rankings.
    played: bool = False
    result_type: MatchResultType = MatchResultType.NORMAL
    stage_item_input1_penalties: int | None = None
    stage_item_input2_penalties: int | None = None

    @property
    def end_time(self) -> datetime_utc:
        assert self.start_time
        return self.start_time + timedelta(minutes=self.duration_minutes + self.margin_minutes)


class MatchInsertable(MatchBaseInsertable):
    stage_item_input1_id: StageItemInputId | None = None
    stage_item_input2_id: StageItemInputId | None = None
    stage_item_input1_winner_from_match_id: MatchId | None = None
    stage_item_input2_winner_from_match_id: MatchId | None = None
    # Third place match: the inputs are the losers of the semifinals
    stage_item_input1_loser_from_match_id: MatchId | None = None
    stage_item_input2_loser_from_match_id: MatchId | None = None


class Match(MatchInsertable):
    id: MatchId
    stage_item_input1: StageItemInput | None = None
    stage_item_input2: StageItemInput | None = None

    def get_winner(self) -> StageItemInput | None:
        """
        The winner of a played match: the team with the higher score, or when the score is
        equal, the winner of the penalty shootout. A match that is still being played (a live
        score) has no winner yet.
        """
        if not self.played:
            return None
        if self.stage_item_input1_score > self.stage_item_input2_score:
            return self.stage_item_input1
        if self.stage_item_input1_score < self.stage_item_input2_score:
            return self.stage_item_input2

        penalties1, penalties2 = self.stage_item_input1_penalties, self.stage_item_input2_penalties
        if self.result_type is MatchResultType.PENALTIES and penalties1 is not None:
            if penalties2 is not None and penalties1 != penalties2:
                return self.stage_item_input1 if penalties1 > penalties2 else self.stage_item_input2

        return None

    def get_loser(self) -> StageItemInput | None:
        winner = self.get_winner()
        if winner is None or self.stage_item_input1 is None:
            return None
        return (
            self.stage_item_input2
            if winner.id == self.stage_item_input1.id
            else self.stage_item_input1
        )


class MatchWithDetails(Match):
    """
    MatchWithDetails has zero or one defined stage item inputs, but not both.
    """

    court: Court | None = None


def get_match_hash(
    stage_item_input1_id: StageItemInputId | None, stage_item_input2_id: StageItemInputId | None
) -> str:
    return f"{stage_item_input1_id}-{stage_item_input2_id}"


class MatchWithDetailsDefinitive(Match):
    stage_item_input1: StageItemInput  # pyrefly: ignore [bad-override]
    stage_item_input2: StageItemInput  # pyrefly: ignore [bad-override]
    court: Court | None = None

    @property
    def stage_item_inputs(self) -> list[StageItemInput]:
        return [self.stage_item_input1, self.stage_item_input2]

    @property
    def stage_item_input_ids(self) -> list[StageItemInputId]:
        return [assert_some(self.stage_item_input1_id), assert_some(self.stage_item_input2_id)]

    def get_input_ids_hashes(self) -> list[str]:
        return [
            get_match_hash(self.stage_item_input1_id, self.stage_item_input2_id),
            get_match_hash(self.stage_item_input2_id, self.stage_item_input1_id),
        ]


class MatchBody(BaseModelORM):
    round_id: RoundId
    stage_item_input1_score: int = Field(0, ge=0)
    stage_item_input2_score: int = Field(0, ge=0)
    court_id: CourtId | None = None
    custom_duration_minutes: int | None = None
    custom_margin_minutes: int | None = None
    # When omitted, the match counts as played once a score other than 0-0 is entered.
    played: bool | None = None
    result_type: MatchResultType = MatchResultType.NORMAL
    stage_item_input1_penalties: int | None = Field(None, ge=0)
    stage_item_input2_penalties: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def check_result(self) -> Self:
        penalties = (self.stage_item_input1_penalties, self.stage_item_input2_penalties)
        equal_score = self.stage_item_input1_score == self.stage_item_input2_score

        if self.result_type is MatchResultType.PENALTIES:
            if None in penalties:
                raise ValueError("Enter the penalty shootout score of both teams")
            if not equal_score:
                raise ValueError("A penalty shootout is only possible when the score is equal")
            if penalties[0] == penalties[1]:
                raise ValueError("A penalty shootout must have a winner")
        elif penalties != (None, None):
            raise ValueError("Penalty scores can only be entered for a penalty shootout")

        if self.result_type is MatchResultType.WALKOVER and equal_score:
            raise ValueError("A walkover must have a winner, e.g. 3-0")
        return self

    def is_played(self, previously_played: bool) -> bool:
        if self.played is not None:
            return self.played
        has_score = self.stage_item_input1_score != 0 or self.stage_item_input2_score != 0
        return previously_played or has_score


class MatchCreateBodyFrontend(BaseModelORM):
    round_id: RoundId
    court_id: CourtId | None = None
    stage_item_input1_id: StageItemInputId | None = None
    stage_item_input2_id: StageItemInputId | None = None
    stage_item_input1_winner_from_match_id: MatchId | None = None
    stage_item_input2_winner_from_match_id: MatchId | None = None


class MatchCreateBody(MatchCreateBodyFrontend):
    duration_minutes: int
    margin_minutes: int
    stage_item_input1_loser_from_match_id: MatchId | None = None
    stage_item_input2_loser_from_match_id: MatchId | None = None
    custom_duration_minutes: int | None = None
    custom_margin_minutes: int | None = None


class MatchRescheduleBody(BaseModelORM):
    old_court_id: CourtId
    old_position: int
    new_court_id: CourtId
    new_position: int


class MatchFilter(BaseModel):
    elo_diff_threshold: int
    only_recommended: bool
    limit: int
    iterations: int


class SuggestedMatch(BaseModel):
    stage_item_input1: StageItemInput
    stage_item_input2: StageItemInput
    elo_diff: Decimal
    swiss_diff: Decimal
    is_recommended: bool
    times_played_sum: int
    player_behind_schedule_count: int

    @property
    def stage_item_input_ids(self) -> list[int]:
        return [self.stage_item_input1.id, self.stage_item_input2.id]
