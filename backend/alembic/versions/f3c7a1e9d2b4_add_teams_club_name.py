"""add teams.club_name, used to keep teams of the same club apart in the group draw

Revision ID: f3c7a1e9d2b4
Revises: e5b8c2f9a1d3
Create Date: 2026-11-11 20:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "f3c7a1e9d2b4"
down_revision: str | None = "e5b8c2f9a1d3"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("club_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("teams", "club_name")
