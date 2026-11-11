"""add tournaments.walkover_goals, teams.withdrawn and teams.checked_in

Revision ID: b5f9c3d7e2a1
Revises: a8d4e2f6c1b3
Create Date: 2026-11-11 23:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "b5f9c3d7e2a1"
down_revision: str | None = "a8d4e2f6c1b3"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column("walkover_goals", sa.Integer(), server_default="3", nullable=False),
    )
    op.add_column("teams", sa.Column("withdrawn", sa.Boolean(), server_default="f", nullable=False))
    op.add_column(
        "teams", sa.Column("checked_in", sa.Boolean(), server_default="f", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("teams", "checked_in")
    op.drop_column("teams", "withdrawn")
    op.drop_column("tournaments", "walkover_goals")
