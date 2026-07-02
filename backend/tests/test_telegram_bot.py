from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest
import httpx

from app.db import Base
from app.models import AppUser
from app.serializers import user_dict
from app.services import tg_client
from app.services.tg_client import TgError


@pytest.fixture
def db():
    # StaticPool: a plain in-memory SQLite DB is per-connection, and TestClient-driven
    # requests (see test_webhook_wrong_secret_returns_403) can check out a different
    # connection from the pool than the one the fixture created — StaticPool pins
    # everything to a single shared connection so the override sees the same data.
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_appuser_has_telegram_id_and_serializes(db):
    u = AppUser(name="Леша", telegram_id="12345")
    db.add(u)
    db.commit()
    d = user_dict(u)
    assert d["telegram_id"] == "12345"


def test_get_me_ok(monkeypatch):
    def handler(request):
        assert "/bottok123/getMe" in request.url.path
        return httpx.Response(200, json={"ok": True, "result": {"username": "mybot"}})

    monkeypatch.setattr(tg_client, "_client_factory",
                        lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    assert tg_client.get_me("tok123")["username"] == "mybot"


def test_get_me_error_raises(monkeypatch):
    def handler(request):
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    monkeypatch.setattr(tg_client, "_client_factory",
                        lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(TgError):
        tg_client.get_me("bad")


from decimal import Decimal
from datetime import date
from app.models import Category, Transaction
from app.services import telegram_bot
from app.services.ai.base import ParsedEntry


def _seed_people_and_cats(db):
    db.add_all([
        Category(name="Кофе", group="wants", sort_order=1),
        AppUser(name="Леша", telegram_id="111"),
    ])
    db.commit()


def test_handle_update_writes_transaction(db, monkeypatch):
    _seed_people_and_cats(db)
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "tok" if "token" in k else "wh")
    monkeypatch.setattr(
        telegram_bot, "parse_with_fallback",
        lambda d, text, ctx: [ParsedEntry(Decimal("360"), "expense", "Кофе", None, None, "кофе", "high")],
    )
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message", lambda token, chat_id, text: sent.append(text))

    update = {"message": {"text": "кофе 360", "chat": {"id": 111}, "from": {"id": 111}}}
    telegram_bot.handle_update(db, update)

    assert db.query(Transaction).count() == 1
    assert sent and "360" in sent[0]


def test_handle_update_rejects_unknown_sender(db, monkeypatch):
    _seed_people_and_cats(db)
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "tok")
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message", lambda token, chat_id, text: sent.append(text))
    update = {"message": {"text": "кофе 360", "chat": {"id": 999}, "from": {"id": 999}}}
    telegram_bot.handle_update(db, update)
    assert db.query(Transaction).count() == 0


def test_webhook_wrong_secret_returns_403(db, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import get_db
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "rightsecret")
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    r = client.post("/api/tg/webhook/wrongsecret", json={})
    app.dependency_overrides.clear()
    assert r.status_code == 403
