"""Alembic migrations on startup and deploy."""

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.db import engine


def run_migrations() -> None:
    """Apply pending migrations. Stamp head if DB was created by create_all."""
    cfg = Config("alembic.ini")
    tables = set(inspect(engine).get_table_names())

    if "alembic_version" not in tables and "app_users" in tables:
        command.stamp(cfg, "head")
        return

    command.upgrade(cfg, "head")
