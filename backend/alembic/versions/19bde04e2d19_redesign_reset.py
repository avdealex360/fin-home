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
    with op.batch_alter_table("income_allocations") as batch_op:
        batch_op.add_column(sa.Column("to_deposit", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("sinking_funds") as batch_op:
        batch_op.add_column(sa.Column("group", sa.String(length=20), nullable=False, server_default="savings"))
        batch_op.add_column(sa.Column("icon", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("color", sa.String(length=16), nullable=True))
        batch_op.drop_column("category_group")
        batch_op.drop_column("linked_category_id")
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
