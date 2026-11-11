from decimal import Decimal
from enum import auto

from heliclockter import datetime_utc
from pydantic import BaseModel, field_validator

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import RankingId, TournamentId
from bracket.utils.types import EnumAutoStr


class Tiebreaker(EnumAutoStr):
    """
    Criteria to order teams with the same number of points, applied in the configured order.
    """

    # Goals scored minus goals conceded
    GOAL_DIFFERENCE = auto()
    GOALS_SCORED = auto()
    # Points in the matches between the teams that are still tied
    HEAD_TO_HEAD = auto()


# Recommended for club cups: head-to-head comes last because it can be circular with 3 teams
DEFAULT_TIEBREAKERS = [Tiebreaker.GOAL_DIFFERENCE, Tiebreaker.GOALS_SCORED, Tiebreaker.HEAD_TO_HEAD]


def check_unique_tiebreakers(tiebreakers: list[Tiebreaker]) -> list[Tiebreaker]:
    if len(set(tiebreakers)) != len(tiebreakers):
        raise ValueError("Each tiebreaker can only be used once")
    return tiebreakers


class RankingInsertable(BaseModel):
    tournament_id: TournamentId
    win_points: Decimal
    draw_points: Decimal
    loss_points: Decimal
    add_score_points: bool
    position: int
    tiebreakers: list[Tiebreaker] = DEFAULT_TIEBREAKERS


class Ranking(BaseModelORM, RankingInsertable):
    id: RankingId
    created: datetime_utc


class RankingBody(BaseModel):
    win_points: Decimal
    draw_points: Decimal
    loss_points: Decimal
    add_score_points: bool
    position: int
    # Required, so that leaving it out doesn't reset a configured order
    tiebreakers: list[Tiebreaker]

    _unique_tiebreakers = field_validator("tiebreakers")(check_unique_tiebreakers)


class RankingCreateBody(BaseModel):
    # Football: 3 points for a win, 1 for a draw
    win_points: Decimal = Decimal("3.0")
    draw_points: Decimal = Decimal("1.0")
    loss_points: Decimal = Decimal("0.0")
    add_score_points: bool = False
    tiebreakers: list[Tiebreaker] = DEFAULT_TIEBREAKERS

    _unique_tiebreakers = field_validator("tiebreakers")(check_unique_tiebreakers)
