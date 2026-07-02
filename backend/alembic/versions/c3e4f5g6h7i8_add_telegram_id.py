"""add telegram_id to app_users

Revision ID: c3e4f5g6h7i8
Revises: b2d3e4f5g6h7
Create Date: 2026-07-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3e4f5g6h7i8"
down_revision: Union[str, None] = "b2d3e4f5g6h7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("app_users") as batch_op:
        batch_op.add_column(sa.Column("telegram_id", sa.String(length=32), nullable=True))
        batch_op.create_unique_constraint("uq_app_users_telegram_id", ["telegram_id"])


def downgrade() -> None:
    with op.batch_alter_table("app_users") as batch_op:
        batch_op.drop_constraint("uq_app_users_telegram_id", type_="unique")
        batch_op.drop_column("telegram_id")
