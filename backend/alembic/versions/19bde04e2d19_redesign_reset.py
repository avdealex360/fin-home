"""redesign reset

Revision ID: 19bde04e2d19
Revises: 003
Create Date: 2026-06-30 02:44:08.761235

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '19bde04e2d19'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("goal_contributions")
    op.drop_table("goals")
    op.add_column("income_allocations", sa.Column("to_deposit", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("sinking_funds", sa.Column("group", sa.String(length=20), nullable=False, server_default="savings"))
    op.add_column("sinking_funds", sa.Column("icon", sa.String(length=64), nullable=True))
    op.add_column("sinking_funds", sa.Column("color", sa.String(length=16), nullable=True))
    op.drop_column("sinking_funds", "category_group")
    op.drop_column("sinking_funds", "linked_category_id")
    op.create_table(
        "deposit_contributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("income_tx_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    raise NotImplementedError("redesign reset is one-way")
