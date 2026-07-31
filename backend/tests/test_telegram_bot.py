from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest
import httpx

from app.db import Base
from app.models import AppUser
from app.serializers import user_dict
from tests.conftest import WS, create_workspace
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
    create_workspace(session)  # id == WS
    yield session
    session.close()


def test_appuser_has_telegram_id_and_serializes(db):
    u = AppUser(workspace_id=WS, name="Леша", telegram_id="12345")
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
        Category(workspace_id=WS, name="Кофе", group="wants", sort_order=1),
        AppUser(workspace_id=WS, name="Леша", telegram_id="111"),
    ])
    db.commit()


def test_handle_update_writes_transaction(db, monkeypatch):
    _seed_people_and_cats(db)
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "tok" if "token" in k else "wh")
    monkeypatch.setattr(
        telegram_bot, "parse_with_fallback",
        lambda d, text, ctx: (
            [ParsedEntry(Decimal("360"), "expense", "Кофе", None, None, "кофе", "high")],
            "yandex",
        ),
    )
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message",
                        lambda token, chat_id, text, reply_markup=None: sent.append(text))

    update = {"message": {"text": "кофе 360", "chat": {"id": 111}, "from": {"id": 111}}}
    telegram_bot.handle_update(db, update)

    assert db.query(Transaction).count() == 1
    assert sent and "360" in sent[0]
    assert "YandexGPT" in sent[0]


def test_handle_update_rejects_unknown_sender(db, monkeypatch):
    _seed_people_and_cats(db)
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "tok")
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message",
                        lambda token, chat_id, text, reply_markup=None: sent.append(text))
    update = {"message": {"text": "кофе 360", "chat": {"id": 999}, "from": {"id": 999}}}
    telegram_bot.handle_update(db, update)
    assert db.query(Transaction).count() == 0


def test_send_message_includes_reply_markup(monkeypatch):
    captured = {}

    def handler(request):
        import json as _json
        captured.update(_json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {}})

    monkeypatch.setattr(tg_client, "_client_factory",
                        lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    tg_client.send_message("tok", 1, "hi", reply_markup={"inline_keyboard": []})
    assert captured["reply_markup"] == {"inline_keyboard": []}


def test_answer_callback_query(monkeypatch):
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        return httpx.Response(200, json={"ok": True, "result": {}})

    monkeypatch.setattr(tg_client, "_client_factory",
                        lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    tg_client.answer_callback_query("tok", "cb1", "ok")
    assert seen["path"].endswith("/answerCallbackQuery")


def test_button_text_triggers_stats(db, monkeypatch):
    _seed_people_and_cats(db)
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "tok")
    monkeypatch.setattr(telegram_bot, "build_digest", lambda d, ws: "ДАЙДЖЕСТ")
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message",
                        lambda token, chat_id, text, reply_markup=None: sent.append(text))
    update = {"message": {"text": "📊 Статистика", "chat": {"id": 111}, "from": {"id": 111}}}
    telegram_bot.handle_update(db, update)
    assert sent == ["ДАЙДЖЕСТ"]


def test_null_category_op_offers_keyboard(db, monkeypatch):
    _seed_people_and_cats(db)
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "tok")
    monkeypatch.setattr(
        telegram_bot, "parse_with_fallback",
        lambda d, text, ctx: (
            [ParsedEntry(Decimal("1840"), "expense", None, None, None, "ремонт газа", "low")],
            "yandex",
        ),
    )
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message",
                        lambda token, chat_id, text, reply_markup=None: sent.append((text, reply_markup)))
    update = {"message": {"text": "ремонт газа 1840", "chat": {"id": 111}, "from": {"id": 111}}}
    telegram_bot.handle_update(db, update)
    kb_sends = [rm for _, rm in sent if rm and "inline_keyboard" in rm]
    assert kb_sends, "expected an inline category keyboard"
    flat = [b for row in kb_sends[0]["inline_keyboard"] for b in row]
    assert any(b["callback_data"].startswith("setcat:") for b in flat)


def test_callback_sets_category(db, monkeypatch):
    _seed_people_and_cats(db)
    tx = Transaction(workspace_id=WS, type="expense", amount=Decimal("1840"), date=date.today(), user_id=None)
    db.add(tx)
    db.commit()
    db.refresh(tx)
    cat = db.query(Category).filter_by(name="Кофе").first()
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "tok")
    monkeypatch.setattr(telegram_bot, "answer_callback_query", lambda *a, **k: None)
    monkeypatch.setattr(telegram_bot, "send_message", lambda *a, **k: None)
    update = {"callback_query": {"id": "cb1", "from": {"id": 111},
              "message": {"chat": {"id": 111}}, "data": f"setcat:{tx.id}:{cat.id}"}}
    telegram_bot.handle_update(db, update)
    db.refresh(tx)
    assert tx.category_id == cat.id


def test_callback_rejects_unknown_sender(db, monkeypatch):
    _seed_people_and_cats(db)
    tx = Transaction(workspace_id=WS, type="expense", amount=Decimal("500"), date=date.today())
    db.add(tx)
    db.commit()
    db.refresh(tx)
    cat = db.query(Category).filter_by(name="Кофе").first()
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "tok")
    answered = []
    monkeypatch.setattr(telegram_bot, "answer_callback_query",
                        lambda token, cb_id, text="": answered.append(text))
    monkeypatch.setattr(telegram_bot, "send_message", lambda *a, **k: None)
    update = {"callback_query": {"id": "cb1", "from": {"id": 999},
              "message": {"chat": {"id": 999}}, "data": f"setcat:{tx.id}:{cat.id}"}}
    telegram_bot.handle_update(db, update)
    db.refresh(tx)
    assert tx.category_id is None


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
