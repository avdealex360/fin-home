from datetime import date, datetime
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AppUser, Category, Transaction, Setting
from app.services import daily_digest
from tests.conftest import WS, create_workspace


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    create_workspace(s)  # id == WS
    cat = Category(workspace_id=WS, name="Продукты", group="needs", sort_order=1)
    s.add(cat)
    s.commit()
    # Fixed date matching the `now` used by the tests below — date.today()
    # here made the suite fail as soon as the calendar month rolled over.
    s.add(Transaction(workspace_id=WS, type="expense", amount=Decimal("1560"), date=date(2026, 7, 2), category_id=cat.id))
    s.commit()
    yield s
    s.close()


def test_digest_caches_for_the_hour(db, monkeypatch):
    calls = {"n": 0}

    def fake_complete(db_, system, user, temperature=0.3):
        calls["n"] += 1
        return "Совет: копи 10%.", "yandex"

    monkeypatch.setattr(daily_digest, "complete_with_fallback", fake_complete)
    first = daily_digest.get_or_build(db, WS, now=datetime(2026, 7, 2, 10, 15))
    second = daily_digest.get_or_build(db, WS, now=datetime(2026, 7, 2, 10, 45))
    assert first == second
    assert calls["n"] == 1  # AI called once, cached after
    assert "YandexGPT" in first
    assert db.query(Setting).filter(Setting.key == "digest.2026-07-02T10").first() is not None


def test_digest_stats_always_fresh(db, monkeypatch):
    monkeypatch.setattr(
        daily_digest, "complete_with_fallback",
        lambda db_, s, u, temperature=0.3: ("Совет дня.", "yandex"),
    )
    first = daily_digest.get_or_build(db, WS, now=datetime(2026, 7, 2, 10, 0))
    assert "1 560" in first or "1560" in first

    db.add(Transaction(workspace_id=WS, type="expense", amount=Decimal("500"), date=date(2026, 7, 2),
                       category_id=db.query(Category).first().id))
    db.commit()

    second = daily_digest.get_or_build(db, WS, now=datetime(2026, 7, 2, 10, 30))
    assert "2 060" in second or "2060" in second
    assert "Совет дня." in second  # tip still cached within the same hour


def test_digest_falls_back_to_static_tip(db, monkeypatch):
    monkeypatch.setattr(daily_digest, "complete_with_fallback", lambda db_, s, u, temperature=0.3: (None, None))
    text = daily_digest.get_or_build(db, WS, now=datetime(2026, 7, 3, 9, 0))
    assert "1 560" in text or "1560" in text  # stats present
    assert len(text) > 0


def test_digest_rebuilds_on_new_day(db, monkeypatch):
    monkeypatch.setattr(daily_digest, "complete_with_fallback", lambda db_, s, u, temperature=0.3: ("tip", "yandex"))
    a = daily_digest.get_or_build(db, WS, now=datetime(2026, 7, 2, 10, 0))
    b = daily_digest.get_or_build(db, WS, now=datetime(2026, 7, 4, 10, 0))
    assert db.query(Setting).filter(Setting.key == "digest.2026-07-04T10").first() is not None


def test_digest_rebuilds_on_new_hour(db, monkeypatch):
    calls = {"n": 0}

    def fake_complete(db_, system, user, temperature=0.3):
        calls["n"] += 1
        return f"tip {calls['n']}", "yandex"

    monkeypatch.setattr(daily_digest, "complete_with_fallback", fake_complete)
    a = daily_digest.get_or_build(db, WS, now=datetime(2026, 7, 2, 10, 59))
    b = daily_digest.get_or_build(db, WS, now=datetime(2026, 7, 2, 11, 0))
    assert calls["n"] == 2  # new hour bucket -> AI called again
    assert "tip 1" in a
    assert "tip 2" in b
    assert db.query(Setting).filter(Setting.key == "digest.2026-07-02T10").first() is not None
    assert db.query(Setting).filter(Setting.key == "digest.2026-07-02T11").first() is not None
