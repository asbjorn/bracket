"""add categories (age classes) for teams and stages

Revision ID: 3f9a6c2d1b7e
Revises: c1ab44651e79
Create Date: 2026-11-11 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "3f9a6c2d1b7e"
down_revision: str | None = "c1ab44651e79"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("tournament_id", sa.BigInteger(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("results_public", sa.Boolean(), server_default="t", nullable=False),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tournament_id", "name"),
    )
    op.create_index(op.f("ix_categories_id"), "categories", ["id"], unique=False)
    op.create_index(
        op.f("ix_categories_tournament_id"), "categories", ["tournament_id"], unique=False
    )

    for table in ("stages", "teams"):
        op.add_column(table, sa.Column("category_id", sa.BigInteger(), nullable=True))
        op.create_foreign_key(
            f"{table}_category_id_fkey", table, "categories", ["category_id"], ["id"]
        )
        op.create_index(op.f(f"ix_{table}_category_id"), table, ["category_id"], unique=False)


def downgrade() -> None:
    for table in ("stages", "teams"):
        op.drop_index(op.f(f"ix_{table}_category_id"), table_name=table)
        op.drop_constraint(f"{table}_category_id_fkey", table, type_="foreignkey")
        op.drop_column(table, "category_id")

    op.drop_index(op.f("ix_categories_tournament_id"), table_name="categories")
    op.drop_index(op.f("ix_categories_id"), table_name="categories")
    op.drop_table("categories")
