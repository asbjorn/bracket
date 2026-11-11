"""add notifications_sent (email queue and log) and tournament_details.email_language

Revision ID: b4c8d2e6f0a7
Revises: a3b7c9d1e5f2
Create Date: 2026-11-12 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "b4c8d2e6f0a7"
down_revision: str | None = "a3b7c9d1e5f2"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("tournament_details", sa.Column("email_language", sa.Text(), nullable=True))
    op.create_table(
        "notifications_sent",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "tournament_id",
            sa.BigInteger(),
            sa.ForeignKey("tournaments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("recipient", sa.Text(), nullable=False),
        sa.Column("reply_to", sa.Text(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tournament_id", "dedupe_key"),
    )
    op.create_index("ix_notifications_sent_status", "notifications_sent", ["status"])


def downgrade() -> None:
    op.drop_index("ix_notifications_sent_status", table_name="notifications_sent")
    op.drop_table("notifications_sent")
    op.drop_column("tournament_details", "email_language")
