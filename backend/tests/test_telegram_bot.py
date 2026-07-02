from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest
import httpx

from app.db import Base
from app.models import AppUser
from app.serializers import user_dict
from app.services import tg_client
from app.services.tg_client import TgError


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
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
