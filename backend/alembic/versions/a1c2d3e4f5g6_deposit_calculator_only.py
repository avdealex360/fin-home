"""deposit becomes a standalone calculator — drop the real-money ledger

Revision ID: a1c2d3e4f5g6
Revises: 19bde04e2d19
Create Date: 2026-07-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c2d3e4f5g6'
down_revision: Union[str, None] = '19bde04e2d19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("deposit_contributions")
    op.drop_table("deposit_snapshots")
    with op.batch_alter_table("income_allocations") as batch_op:
        batch_op.drop_column("to_deposit")


def downgrade() -> None:
    raise NotImplementedError("deposit calculator migration is one-way")
