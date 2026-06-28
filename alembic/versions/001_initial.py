"""initial

Revision ID: 001
Revises:
Create Date: 2026-06-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("group", sa.String(length=20), nullable=False),
        sa.Column("is_hidden", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "debts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("remaining", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("monthly_payment", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("interest_rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("target_close_date", sa.Date(), nullable=True),
        sa.Column("grace_period_end", sa.Date(), nullable=True),
        sa.Column("next_payment_date", sa.Date(), nullable=True),
        sa.Column("is_closed", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("target_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("current_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("monthly_contribution", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("linked_account_name", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "monthly_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("expected_income", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year", "month", name="uq_plan_year_month"),
    )
    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "deposit_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("balance", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "category_limits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("limit_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["monthly_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "category_id", name="uq_plan_category"),
    )
    op.create_table(
        "debt_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("debt_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["debt_id"], ["debts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "goal_contributions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("base_amount_eur", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("goal_contributions")
    op.drop_table("debt_payments")
    op.drop_table("category_limits")
    op.drop_table("deposit_snapshots")
    op.drop_table("settings")
    op.drop_table("monthly_plans")
    op.drop_table("goals")
    op.drop_table("debts")
    op.drop_table("categories")
    op.drop_table("app_users")
