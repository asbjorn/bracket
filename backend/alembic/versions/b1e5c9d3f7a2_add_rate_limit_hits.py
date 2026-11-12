"""add rate_limit_hits: rate limits shared by all server processes

Revision ID: b1e5c9d3f7a2
Revises: a9c4e7b2d6f1
Create Date: 2026-11-12 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "b1e5c9d3f7a2"
down_revision: str | None = "a9c4e7b2d6f1"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_hits",
        sa.Column("bucket", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("bucket", "key_hash", "window_start"),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_hits")
