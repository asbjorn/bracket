"""add matches.stage_item_input{1,2}_loser_from_match_id for third place matches

Revision ID: c4f1a7e8b3d2
Revises: b7e3c9d4f2a6
Create Date: 2026-11-11 16:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "c4f1a7e8b3d2"
down_revision: str | None = "b7e3c9d4f2a6"
branch_labels: str | None = None
depends_on: str | None = None

COLUMNS = ("stage_item_input1_loser_from_match_id", "stage_item_input2_loser_from_match_id")


def upgrade() -> None:
    for column in COLUMNS:
        op.add_column("matches", sa.Column(column, sa.BigInteger(), nullable=True))
        op.create_foreign_key(f"matches_{column}_fkey", "matches", "matches", [column], ["id"])


def downgrade() -> None:
    for column in COLUMNS:
        op.drop_constraint(f"matches_{column}_fkey", "matches", type_="foreignkey")
        op.drop_column("matches", column)
