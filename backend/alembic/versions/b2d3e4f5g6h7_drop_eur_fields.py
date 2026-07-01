"""drop EUR conversion fields — all income/expenses are in rubles

Revision ID: b2d3e4f5g6h7
Revises: a1c2d3e4f5g6
Create Date: 2026-07-01 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2d3e4f5g6h7'
down_revision: Union[str, None] = 'a1c2d3e4f5g6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_column("base_amount_eur")
        batch_op.drop_column("exchange_rate")


def downgrade() -> None:
    raise NotImplementedError("drop EUR fields migration is one-way")
