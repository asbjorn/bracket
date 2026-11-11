"""add ranking tiebreakers and goals/position to stage item inputs

Revision ID: a2d8f5c3e1b9
Revises: 7c4e1a9b2d5f
Create Date: 2026-11-11 14:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "a2d8f5c3e1b9"
down_revision: str | None = "7c4e1a9b2d5f"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "rankings",
        sa.Column(
            "tiebreakers",
            ARRAY(sa.Text()),
            server_default=sa.text("'{GOAL_DIFFERENCE,GOALS_SCORED,HEAD_TO_HEAD}'::text[]"),
            nullable=False,
        ),
    )
    op.add_column(
        "stage_item_inputs",
        sa.Column("goals_for", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "stage_item_inputs",
        sa.Column("goals_against", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("stage_item_inputs", sa.Column("position", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("stage_item_inputs", "position")
    op.drop_column("stage_item_inputs", "goals_against")
    op.drop_column("stage_item_inputs", "goals_for")
    op.drop_column("rankings", "tiebreakers")
