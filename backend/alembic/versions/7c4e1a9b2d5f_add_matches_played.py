"""add matches.played

Revision ID: 7c4e1a9b2d5f
Revises: 3f9a6c2d1b7e
Create Date: 2026-11-11 13:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "7c4e1a9b2d5f"
down_revision: str | None = "3f9a6c2d1b7e"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("played", sa.Boolean(), server_default="f", nullable=False))
    # Before this column existed, a match with a score was considered played.
    op.execute(
        """
        UPDATE matches
        SET played = true
        WHERE stage_item_input1_score <> 0 OR stage_item_input2_score <> 0
        """
    )


def downgrade() -> None:
    op.drop_column("matches", "played")
