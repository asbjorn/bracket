"""add stage_item_inputs.best_from_stage_id and best_rank (best placed across groups)

Revision ID: d9a2b6c1e4f7
Revises: c4f1a7e8b3d2
Create Date: 2026-11-11 17:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "d9a2b6c1e4f7"
down_revision: str | None = "c4f1a7e8b3d2"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "stage_item_inputs", sa.Column("best_from_stage_id", sa.BigInteger(), nullable=True)
    )
    op.create_foreign_key(
        "stage_item_inputs_best_from_stage_id_fkey",
        "stage_item_inputs",
        "stages",
        ["best_from_stage_id"],
        ["id"],
    )
    op.add_column("stage_item_inputs", sa.Column("best_rank", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("stage_item_inputs", "best_rank")
    op.drop_constraint(
        "stage_item_inputs_best_from_stage_id_fkey", "stage_item_inputs", type_="foreignkey"
    )
    op.drop_column("stage_item_inputs", "best_from_stage_id")
