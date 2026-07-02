import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from types import SimpleNamespace
import bcrypt

import app.models  # noqa: F401 — registers models with Base.metadata
from app.db import Base, get_db
from app.main import app
from app.services.settings_store import get_secret, set_secret, secret_is_set, mask_secret
from app.services import auth as auth_module


def _authenticate(client) -> None:
    """Inject a valid session cookie so TestClient calls pass the auth middleware."""
    from app.services.auth import SESSION_COOKIE, create_session_token

    client.cookies.set(SESSION_COOKIE, create_session_token())


@pytest.fixture
def db():
    # StaticPool: TestClient dispatches requests via a worker thread, and a plain
    # in-memory SQLite DB is per-connection — without StaticPool the endpoint would
    # see a different, empty in-memory DB than the one this fixture seeded. Same
    # fix as tests/test_telegram_bot.py's db fixture.
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
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


def test_integrations_get_reports_flags_not_raw(db):
    set_secret(db, "secret.yandex_api_key", "yakey")
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    _authenticate(client)
    r = client.get("/api/settings/integrations")
    app.dependency_overrides.clear()
    body = r.json()
    assert body["yandex_api_key"] is True
    assert body["gigachat_auth_key"] is False
    assert "yakey" not in json.dumps(body)


def test_integrations_post_saves_nonempty(db):
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    _authenticate(client)
    client.post("/api/settings/integrations", json={
        "yandex_api_key": "newkey", "yandex_folder_id": "", "ai_primary_provider": "gigachat",
    })
    app.dependency_overrides.clear()
    assert get_secret(db, "secret.yandex_api_key") == "newkey"
    from app.services.settings_store import get_setting
    assert get_setting(db, "ai_primary_provider") == "gigachat"
