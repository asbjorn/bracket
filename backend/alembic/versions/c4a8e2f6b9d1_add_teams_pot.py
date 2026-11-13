"""add teams.pot: the seeding pot of a team in the group draw

Revision ID: c4a8e2f6b9d1
Revises: b1e5c9d3f7a2
Create Date: 2026-11-13 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "c4a8e2f6b9d1"
down_revision: str | None = "b1e5c9d3f7a2"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("pot", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("teams", "pot")
