"""add matches.result_type and penalty scores

Revision ID: b7e3c9d4f2a6
Revises: a2d8f5c3e1b9
Create Date: 2026-11-11 15:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "b7e3c9d4f2a6"
down_revision: str | None = "a2d8f5c3e1b9"
branch_labels: str | None = None
depends_on: str | None = None

result_type = ENUM(
    "NORMAL", "EXTRA_TIME", "PENALTIES", "WALKOVER", name="match_result_type", create_type=True
)


def upgrade() -> None:
    result_type.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "matches",
        sa.Column("result_type", result_type, server_default="NORMAL", nullable=False),
    )
    op.add_column("matches", sa.Column("stage_item_input1_penalties", sa.Integer(), nullable=True))
    op.add_column("matches", sa.Column("stage_item_input2_penalties", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("matches", "stage_item_input2_penalties")
    op.drop_column("matches", "stage_item_input1_penalties")
    op.drop_column("matches", "result_type")
    result_type.drop(op.get_bind())
