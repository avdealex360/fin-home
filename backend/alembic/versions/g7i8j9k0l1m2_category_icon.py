"""categories.icon — per-category user icon override

Revision ID: g7i8j9k0l1m2
Revises: f6h7i8j9k0l1
Create Date: 2026-08-06 00:00:00.000000

Icons used to be derived from the category name only; a user-picked icon
is stored here and takes precedence over the name-based mapping.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g7i8j9k0l1m2"
down_revision: Union[str, None] = "f6h7i8j9k0l1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("categories", sa.Column("icon", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("categories", "icon")
