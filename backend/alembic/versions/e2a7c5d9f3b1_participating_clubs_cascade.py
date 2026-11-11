"""participating clubs are deleted together with their tournament

Revision ID: e2a7c5d9f3b1
Revises: d6e1f4a8b2c7
Create Date: 2026-11-12 10:30:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "e2a7c5d9f3b1"
down_revision: str | None = "d6e1f4a8b2c7"
branch_labels: str | None = None
depends_on: str | None = None

NAME = "participating_clubs_tournament_id_fkey"


def upgrade() -> None:
    op.drop_constraint(NAME, "participating_clubs", type_="foreignkey")
    op.create_foreign_key(
        NAME, "participating_clubs", "tournaments", ["tournament_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint(NAME, "participating_clubs", type_="foreignkey")
    op.create_foreign_key(NAME, "participating_clubs", "tournaments", ["tournament_id"], ["id"])
