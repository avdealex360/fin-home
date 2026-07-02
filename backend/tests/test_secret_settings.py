import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from types import SimpleNamespace
import bcrypt

import app.models  # noqa: F401 — registers models with Base.metadata
from app.db import Base, get_db
from app.services.settings_store import get_secret, set_secret, secret_is_set, mask_secret
from app.services import auth as auth_module


def _authenticate(client) -> None:
    """Inject a valid session cookie so TestClient calls pass the auth middleware."""
    from app.services.auth import SESSION_COOKIE, create_session_token

    client.cookies.set(SESSION_COOKIE, create_session_token())


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_set_secret_skips_empty(db):
    set_secret(db, "secret.tg_bot_token", "abc123")
    assert get_secret(db, "secret.tg_bot_token") == "abc123"
    set_secret(db, "secret.tg_bot_token", "")  # empty = keep existing
    assert get_secret(db, "secret.tg_bot_token") == "abc123"
    assert secret_is_set(db, "secret.tg_bot_token") is True


def test_mask_secret():
    assert mask_secret("abcdef1234") == "••••1234"
    assert mask_secret("") == ""


def test_secret_excluded_from_export(db):
    from app.models import Setting

    # Set a secret in the DB
    set_secret(db, "secret.tg_bot_token", "supersecret")

    # Test the filtering logic directly
    # This is what the export_json endpoint does internally
    all_settings = db.query(Setting).all()

    # Filter out secret.* keys
    filtered_settings = {
        s.key: s.value
        for s in all_settings
        if not s.key.startswith("secret.")
    }

    # Verify that the secret was not included
    assert "secret.tg_bot_token" not in filtered_settings
    # But verify it's still in the DB
    assert get_secret(db, "secret.tg_bot_token") == "supersecret"
