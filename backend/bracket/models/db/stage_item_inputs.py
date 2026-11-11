from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from bracket.models.db.shared import BaseModelORM
from bracket.models.db.team import Team
from bracket.utils.id_types import StageId, StageItemId, StageItemInputId, TeamId, TournamentId


class StageItemInputBase(BaseModelORM):
    id: StageItemInputId
    slot: int
    tournament_id: TournamentId
    stage_item_id: StageItemId | None = None


class StageItemInputGeneric(BaseModel):
    points: Decimal = Decimal("0.0")
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    # Place in the ranking of the stage item (1 = first), after applying the tiebreakers
    position: int | None = None
    # Drawing of lots, entered by the organiser (lower is better)
    lot_number: int | None = None

    @property
    def elo(self) -> Decimal:
        """
        For now, ELO is saved as points.
        """
        return self.points


def hash_stage_item_input(
    self: StageItemInputTentative
    | StageItemInputBestOf
    | StageItemInputFinal
    | StageItemInputEmpty,
) -> int:
    return (
        self.team_id,
        self.winner_from_stage_item_id,
        self.winner_position,
        self.best_from_stage_id,
        self.best_rank,
    ).__hash__()


class StageItemInputTentative(StageItemInputBase, StageItemInputGeneric):
    team_id: None = None
    winner_from_stage_item_id: StageItemId
    winner_position: int = Field(ge=1)
    best_from_stage_id: None = None
    best_rank: None = None

    def get_lookup_key(self) -> tuple[StageItemId, int]:
        return self.winner_from_stage_item_id, self.winner_position

    __hash__ = hash_stage_item_input


class StageItemInputBestOf(StageItemInputBase, StageItemInputGeneric):
    """
    The `best_rank`-th best team of all teams at `winner_position` in the groups of a stage,
    e.g. the 2nd best third placed team. Determined when the next stage is activated.
    """

    team_id: None = None
    winner_from_stage_item_id: None = None
    winner_position: int = Field(ge=1)
    best_from_stage_id: StageId
    best_rank: int = Field(ge=1)

    __hash__ = hash_stage_item_input


class StageItemInputFinal(StageItemInputBase, StageItemInputGeneric):
    team_id: TeamId
    winner_from_stage_item_id: StageItemId | None = None
    winner_position: int | None = None
    best_from_stage_id: StageId | None = None
    best_rank: int | None = None
    team: Team

    __hash__ = hash_stage_item_input


class StageItemInputEmpty(StageItemInputBase, StageItemInputGeneric):
    team_id: None = None
    winner_from_stage_item_id: None = None
    winner_position: None = None
    best_from_stage_id: None = None
    best_rank: None = None

    __hash__ = hash_stage_item_input


StageItemInput = (
    StageItemInputTentative | StageItemInputBestOf | StageItemInputFinal | StageItemInputEmpty
)


class StageItemInputCreateBodyTentative(BaseModel):
    slot: int
    winner_from_stage_item_id: StageItemId
    winner_position: int = Field(ge=1)


class StageItemInputCreateBodyBestOf(BaseModel):
    slot: int
    best_from_stage_id: StageId
    winner_position: int = Field(ge=1)
    best_rank: int = Field(ge=1)


class StageItemInputCreateBodyFinal(BaseModel):
    slot: int
    team_id: TeamId


class StageItemInputCreateBodyEmpty(BaseModel):
    slot: int


StageItemInputCreateBody = (
    StageItemInputCreateBodyTentative
    | StageItemInputCreateBodyBestOf
    | StageItemInputCreateBodyFinal
    | StageItemInputCreateBodyEmpty
)


class StageItemInputUpdateBodyTentative(BaseModelORM):
    winner_from_stage_item_id: StageItemId
    winner_position: int = Field(ge=1)


class StageItemInputUpdateBodyFinal(BaseModelORM):
    team_id: TeamId


class StageItemInputUpdateBodyEmpty(BaseModelORM):
    team_id: None = None
    winner_from_stage_item_id: None = None
    winner_position: None = None


StageItemInputUpdateBody = (
    StageItemInputUpdateBodyTentative
    | StageItemInputUpdateBodyFinal
    | StageItemInputUpdateBodyEmpty
)


class StageItemInputInsertable(BaseModel):
    slot: int
    team_id: TeamId | None = None
    tournament_id: TournamentId
    stage_item_id: StageItemId


class StageItemInputOptionFinal(BaseModel):
    team_id: TeamId
    already_taken: bool


class StageItemInputOptionTentative(BaseModel):
    winner_from_stage_item_id: StageItemId
    winner_position: int
    already_taken: bool
