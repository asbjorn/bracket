"""add tournament_details: cup facts for the application to the district (krets)

Revision ID: a3b7c9d1e5f2
Revises: f1d6b8c4e3a5
Create Date: 2026-11-12 10:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "a3b7c9d1e5f2"
down_revision: str | None = "f1d6b8c4e3a5"
branch_labels: str | None = None
depends_on: str | None = None

TEXT_COLUMNS = (
    "organiser_club",
    "contact_name",
    "contact_phone",
    "contact_email",
    "jury_chair_name",
    "jury_chair_phone",
    "venue",
    "rules_summary",
    "notes",
)


def upgrade() -> None:
    op.create_table(
        "tournament_details",
        sa.Column(
            "tournament_id",
            sa.BigInteger(),
            sa.ForeignKey("tournaments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        *(sa.Column(name, sa.Text(), nullable=True) for name in TEXT_COLUMNS),
    )


def downgrade() -> None:
    op.drop_table("tournament_details")
