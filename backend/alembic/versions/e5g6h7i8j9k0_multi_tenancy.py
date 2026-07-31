"""multi-tenancy: workspaces, accounts, invites, workspace_id everywhere

Revision ID: e5g6h7i8j9k0
Revises: d4f5g6h7i8j9
Create Date: 2026-07-31 00:00:00.000000

Existing data is adopted into a default workspace (id=1, «Семья»). The admin
account itself is created at startup by seed.ensure_admin_account from env.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5g6h7i8j9k0"
down_revision: Union[str, None] = "d4f5g6h7i8j9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Root tables that get a workspace_id column.
_SCOPED_TABLES = ["app_users", "categories", "sinking_funds", "transactions", "monthly_plans", "debts"]


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("onboarded", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=100), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=200), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(length=64), nullable=False, unique=True),
        sa.Column("label", sa.String(length=200), nullable=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("used_by_account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # Adopt existing data into a default workspace. `onboarded` moves from the
    # old settings KV into the workspace row.
    has_data = any(
        bind.execute(sa.text(f"SELECT 1 FROM {t} LIMIT 1")).first() is not None
        for t in _SCOPED_TABLES
    )
    has_settings = bind.execute(sa.text("SELECT 1 FROM settings LIMIT 1")).first() is not None
    onboarded_row = bind.execute(sa.text("SELECT value FROM settings WHERE key='onboarded'")).first()
    onboarded = onboarded_row[0] if onboarded_row else ""
    if has_data or has_settings or onboarded:
        bind.execute(
            sa.text("INSERT INTO workspaces (id, name, onboarded, created_at) VALUES (1, 'Семья', :onb, CURRENT_TIMESTAMP)"),
            {"onb": onboarded},
        )

    for table in _SCOPED_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("workspace_id", sa.Integer(), nullable=True))
        bind.execute(sa.text(f"UPDATE {table} SET workspace_id = 1"))
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("workspace_id", nullable=False, existing_type=sa.Integer())
            batch_op.create_foreign_key(f"fk_{table}_workspace", "workspaces", ["workspace_id"], ["id"])

    # monthly_plans unique constraint becomes (workspace_id, year, month)
    with op.batch_alter_table("monthly_plans") as batch_op:
        batch_op.drop_constraint("uq_plan_year_month", type_="unique")
        batch_op.create_unique_constraint("uq_plan_year_month", ["workspace_id", "year", "month"])

    # settings: key-PK KV -> (id, workspace_id, key, value). secret.* and the
    # AI/bot toggles stay global (NULL); the rest belongs to workspace 1;
    # the old onboarded row is dropped (moved to the workspace).
    op.rename_table("settings", "settings_old")
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.UniqueConstraint("workspace_id", "key", name="uq_settings_ws_key"),
    )
    bind.execute(sa.text(
        "INSERT INTO settings (workspace_id, key, value) "
        "SELECT CASE WHEN key LIKE 'secret.%' OR key LIKE 'digest.%' "
        "  OR key IN ('ai_primary_provider', 'tg_bot_enabled') THEN NULL ELSE 1 END, "
        "key, value FROM settings_old WHERE key != 'onboarded'"
    ))
    op.drop_table("settings_old")


def downgrade() -> None:
    raise NotImplementedError("multi-tenancy migration is one-way")
