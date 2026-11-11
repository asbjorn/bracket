from decimal import Decimal

from pydantic import BaseModel

START_ELO = Decimal("1200")


class TeamStatistics(BaseModel):
    wins: int = 0
    draws: int = 0
    losses: int = 0
    points: Decimal = Decimal("0.00")
    goals_for: int = 0
    goals_against: int = 0
    position: int | None = None

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against
