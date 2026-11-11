"""add the tournament announcement (public banner) and rules sheet

Revision ID: c2e8f4a6b9d1
Revises: b5f9c3d7e2a1
Create Date: 2026-11-12 10:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "c2e8f4a6b9d1"
down_revision: str | None = "b5f9c3d7e2a1"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("tournaments", sa.Column("announcement_text", sa.Text(), nullable=True))
    op.add_column("tournaments", sa.Column("announcement_level", sa.Text(), nullable=True))
    op.add_column(
        "tournaments", sa.Column("announcement_until", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("tournaments", sa.Column("rules_text", sa.Text(), nullable=True))


def downgrade() -> None:
    for column in ("rules_text", "announcement_until", "announcement_level", "announcement_text"):
        op.drop_column("tournaments", column)
