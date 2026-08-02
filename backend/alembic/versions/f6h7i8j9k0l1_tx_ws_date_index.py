"""index transactions (workspace_id, date)

Revision ID: f6h7i8j9k0l1
Revises: e5g6h7i8j9k0
Create Date: 2026-08-02 00:00:00.000000

Every hot query (dashboard, carryover, analytics, transaction list) filters
by workspace_id and usually by date; SQLite FKs create no index, so without
this each of them is a full table scan.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "f6h7i8j9k0l1"
down_revision: Union[str, None] = "e5g6h7i8j9k0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_transactions_ws_date", "transactions", ["workspace_id", "date"])


def downgrade() -> None:
    op.drop_index("ix_transactions_ws_date", table_name="transactions")
