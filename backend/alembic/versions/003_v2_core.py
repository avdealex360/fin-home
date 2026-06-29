"""v2 core: sinking funds, income allocations, envelope budgeting

Revision ID: 003
Revises: 002
Create Date: 2026-06-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sinking_funds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("target_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("current_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("monthly_contribution", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("category_group", sa.String(length=20), nullable=False),
        sa.Column("is_rolling", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("linked_category_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["linked_category_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "sinking_fund_contributions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fund_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["fund_id"], ["sinking_funds.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "income_allocations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("income_tx_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("fund_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("allocated_at", sa.DateTime(), nullable=False),
        sa.Column("allocation_level", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["fund_id"], ["sinking_funds.id"]),
        sa.ForeignKeyConstraint(["income_tx_id"], ["transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("categories") as batch_op:
        batch_op.add_column(sa.Column("allocation_level", sa.Integer(), nullable=True))

    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(sa.Column("exchange_rate", sa.Numeric(precision=12, scale=4), nullable=True))
        batch_op.add_column(
            sa.Column("is_fully_allocated", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("is_sinking_fund_spend", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("fund_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_transactions_fund_id", "sinking_funds", ["fund_id"], ["id"])

    with op.batch_alter_table("goals") as batch_op:
        batch_op.add_column(sa.Column("linked_category_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_goals_linked_category_id", "categories", ["linked_category_id"], ["id"]
        )

    with op.batch_alter_table("monthly_plans") as batch_op:
        batch_op.add_column(sa.Column("is_closed", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("closed_at", sa.DateTime(), nullable=True))

    with op.batch_alter_table("category_limits") as batch_op:
        batch_op.add_column(
            sa.Column("carried_over", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0")
        )

    with op.batch_alter_table("debts") as batch_op:
        batch_op.add_column(sa.Column("priority_rank", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("debts") as batch_op:
        batch_op.drop_column("priority_rank")

    with op.batch_alter_table("category_limits") as batch_op:
        batch_op.drop_column("carried_over")

    with op.batch_alter_table("monthly_plans") as batch_op:
        batch_op.drop_column("closed_at")
        batch_op.drop_column("is_closed")

    with op.batch_alter_table("goals") as batch_op:
        batch_op.drop_constraint("fk_goals_linked_category_id", type_="foreignkey")
        batch_op.drop_column("linked_category_id")

    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_constraint("fk_transactions_fund_id", type_="foreignkey")
        batch_op.drop_column("fund_id")
        batch_op.drop_column("is_sinking_fund_spend")
        batch_op.drop_column("is_fully_allocated")
        batch_op.drop_column("exchange_rate")

    with op.batch_alter_table("categories") as batch_op:
        batch_op.drop_column("allocation_level")

    op.drop_table("income_allocations")
    op.drop_table("sinking_fund_contributions")
    op.drop_table("sinking_funds")
