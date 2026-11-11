from enum import auto
from typing import Annotated

from heliclockter import datetime_utc
from pydantic import BaseModel, Field, StringConstraints

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import (
    JuryDecisionId,
    MatchCardId,
    MatchId,
    PlayerId,
    TeamId,
    TournamentId,
    UserId,
)
from bracket.utils.types import EnumAutoStr

PlayerName = Annotated[str, StringConstraints(min_length=1, max_length=60, strip_whitespace=True)]


class CardType(EnumAutoStr):
    YELLOW = auto()
    YELLOW_RED = auto()  # Second yellow in a match: counts as a red card
    RED = auto()


class SuspensionReason(EnumAutoStr):
    RED_CARD = auto()
    YELLOW_CARDS = auto()


class MatchCardBody(BaseModelORM):
    team_id: TeamId
    player_name: PlayerName
    player_id: PlayerId | None = None
    card_type: CardType
    minute: int | None = Field(None, ge=0, le=200)
    note: Annotated[str, StringConstraints(max_length=300, strip_whitespace=True)] | None = None


class MatchCard(MatchCardBody):
    id: MatchCardId
    tournament_id: TournamentId
    match_id: MatchId
    created: datetime_utc


class DisciplineSettingsBody(BaseModelORM):
    suspension_matches_per_red: int = Field(1, ge=0, le=5)
    # E.g. 3: every third yellow card gives a one-match suspension; None: yellows don't count
    yellow_cards_for_suspension: int | None = Field(None, ge=2, le=10)


class JuryDecisionBody(BaseModelORM):
    text: Annotated[str, StringConstraints(min_length=1, max_length=2000, strip_whitespace=True)]
    match_id: MatchId | None = None
    team_id: TeamId | None = None
    # The card it is about; its suspension changes by `suspension_change` matches
    card_id: MatchCardId | None = None
    # Jury members who took the decision
    member_ids: list[int] = Field(default=[], max_length=10)
    suspension_change: int = Field(0, ge=-10, le=10)


class JuryDecision(JuryDecisionBody):
    id: JuryDecisionId
    tournament_id: TournamentId
    decided_at: datetime_utc
    decided_by: UserId | None = None


class Suspension(BaseModel):
    team_id: TeamId
    player_name: str
    reason: SuspensionReason
    # The card that gave the suspension (for yellow cards: the last one)
    card_id: MatchCardId
    # The team's next matches the player sits out (fewer when the team has no more matches)
    match_ids: list[MatchId]
    matches: int


class DisciplineOverview(BaseModel):
    settings: DisciplineSettingsBody
    cards: list[MatchCard]
    suspensions: list[Suspension]
    decisions: list[JuryDecision]


class SuspendedPlayer(BaseModel):
    """For the pitch page and printed cards: who may not play in this match."""

    team_id: TeamId
    player_name: str
