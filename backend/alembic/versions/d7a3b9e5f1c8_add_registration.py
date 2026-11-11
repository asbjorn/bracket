"""add registration: sign-up settings per class, registration status of teams and the
contact details of registered teams (kept in their own table, never public)

Revision ID: d7a3b9e5f1c8
Revises: c2e8f4a6b9d1
Create Date: 2026-11-12 10:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "d7a3b9e5f1c8"
down_revision: str | None = "c2e8f4a6b9d1"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("registration_open", sa.Boolean(), server_default="f", nullable=False),
    )
    op.add_column(
        "categories", sa.Column("registration_deadline", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("categories", sa.Column("max_teams", sa.Integer(), nullable=True))
    op.add_column("categories", sa.Column("entry_fee", sa.Integer(), nullable=True))
    op.add_column(
        "teams",
        sa.Column("registration_status", sa.Text(), server_default="APPROVED", nullable=False),
    )
    op.create_index("ix_teams_registration_status", "teams", ["registration_status"])
    op.create_table(
        "team_registrations",
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tournament_id",
            sa.BigInteger(),
            sa.ForeignKey("tournaments.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("contact_name", sa.Text(), nullable=True),
        sa.Column("contact_email", sa.Text(), nullable=True),
        sa.Column("contact_phone", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid", sa.Boolean(), server_default="f", nullable=False),
        sa.Column("squad_reported", sa.Boolean(), server_default="f", nullable=False),
    )


def downgrade() -> None:
    op.drop_table("team_registrations")
    op.drop_index("ix_teams_registration_status", table_name="teams")
    op.drop_column("teams", "registration_status")
    for column in ("entry_fee", "max_teams", "registration_deadline", "registration_open"):
        op.drop_column("categories", column)
