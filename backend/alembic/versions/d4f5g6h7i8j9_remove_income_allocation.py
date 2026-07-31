"""remove income allocation feature

Revision ID: d4f5g6h7i8j9
Revises: c3e4f5g6h7i8
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4f5g6h7i8j9"
down_revision: Union[str, None] = "c3e4f5g6h7i8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("income_allocations")
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_column("is_fully_allocated")
    with op.batch_alter_table("categories") as batch_op:
        batch_op.drop_column("allocation_level")


def downgrade() -> None:
    with op.batch_alter_table("categories") as batch_op:
        batch_op.add_column(sa.Column("allocation_level", sa.Integer(), nullable=True))
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(
            sa.Column("is_fully_allocated", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    op.create_table(
        "income_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("income_tx_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("sinking_funds.id"), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("allocated_at", sa.DateTime(), nullable=True),
        sa.Column("allocation_level", sa.Integer(), nullable=False),
    )
