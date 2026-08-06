"""Day-cached AI market overview for the invest section."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.db import Base
from app.services import invest_overview as ov
from app.services.moex import MoexError, Quote
from app.services.settings_store import set_secret
from tests.conftest import create_workspace

DISCLAIMER = "Не является индивидуальной инвестиционной рекомендацией"


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ov.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def ws(db):
    return create_workspace(db).id


def _configure_ai(db):
    set_secret(db, "secret.yandex_api_key", "k")
    set_secret(db, "secret.yandex_folder_id", "f")


def _stub_quotes(monkeypatch):
    monkeypatch.setattr(ov, "get_quotes", lambda tickers: [
        Quote("IMOEX", "Индекс МосБиржи", 3214.5, 0.8),
        Quote("SBER", "Сбербанк", 312.4, -0.4),
    ])


def test_builds_once_per_day_and_caches(db, ws, monkeypatch):
    _configure_ai(db)
    _stub_quotes(monkeypatch)
    calls = []

    def fake_complete(d, system, user, temperature=0.3):
        calls.append(user)
        return "Рынок сегодня подрос.", "yandex"
    monkeypatch.setattr(ov, "complete_with_fallback", fake_complete)

    now = datetime(2026, 8, 6, 10, 0)
    first = ov.get_or_build(db, ws, now=now)
    second = ov.get_or_build(db, ws, now=now.replace(hour=18))

    assert len(calls) == 1
    assert first["configured"] is True
    assert "Рынок сегодня подрос." in first["text"]
    assert DISCLAIMER in first["text"]
    assert second["text"] == first["text"]
    # market data reaches the prompt
    assert "SBER" in calls[0] or "Сбербанк" in calls[0]


def test_new_day_rebuilds(db, ws, monkeypatch):
    _configure_ai(db)
    _stub_quotes(monkeypatch)
    calls = []
    monkeypatch.setattr(ov, "complete_with_fallback",
                        lambda d, s, u, temperature=0.3: (calls.append(u) or "Обзор.", "yandex"))
    ov.get_or_build(db, ws, now=datetime(2026, 8, 6, 10, 0))
    ov.get_or_build(db, ws, now=datetime(2026, 8, 7, 10, 0))
    assert len(calls) == 2


def test_without_ai_keys_reports_unconfigured(db, ws, monkeypatch):
    _stub_quotes(monkeypatch)
    monkeypatch.setattr(ov, "complete_with_fallback",
                        lambda *a, **k: pytest.fail("AI must not be called"))
    out = ov.get_or_build(db, ws, now=datetime(2026, 8, 6, 10, 0))
    assert out["configured"] is False
    assert out["text"] is None


def test_moex_failure_returns_no_text_without_crash(db, ws, monkeypatch):
    _configure_ai(db)
    monkeypatch.setattr(ov, "get_quotes",
                        lambda tickers: (_ for _ in ()).throw(MoexError("down")))
    out = ov.get_or_build(db, ws, now=datetime(2026, 8, 6, 10, 0))
    assert out["text"] is None
    assert out["configured"] is True


def test_ai_failure_returns_none_text(db, ws, monkeypatch):
    _configure_ai(db)
    _stub_quotes(monkeypatch)
    monkeypatch.setattr(ov, "complete_with_fallback",
                        lambda d, s, u, temperature=0.3: (None, None))
    out = ov.get_or_build(db, ws, now=datetime(2026, 8, 6, 10, 0))
    assert out["text"] is None
    assert out["configured"] is True
