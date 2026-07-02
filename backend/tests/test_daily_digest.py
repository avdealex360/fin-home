from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AppUser, Category, Transaction, Setting
from app.services import daily_digest


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    cat = Category(name="Продукты", group="needs", sort_order=1)
    s.add(cat)
    s.commit()
    s.add(Transaction(type="expense", amount=Decimal("1560"), date=date.today(), category_id=cat.id))
    s.commit()
    yield s
    s.close()


def test_digest_caches_for_the_day(db, monkeypatch):
    calls = {"n": 0}

    def fake_complete(db_, system, user):
        calls["n"] += 1
        return "Совет: копи 10%."

    monkeypatch.setattr(daily_digest, "complete_with_fallback", fake_complete)
    first = daily_digest.get_or_build(db, today=date(2026, 7, 2))
    second = daily_digest.get_or_build(db, today=date(2026, 7, 2))
    assert first == second
    assert calls["n"] == 1  # AI called once, cached after
    assert db.query(Setting).filter(Setting.key == "digest.2026-07-02").first() is not None


def test_digest_falls_back_to_static_tip(db, monkeypatch):
    monkeypatch.setattr(daily_digest, "complete_with_fallback", lambda db_, s, u: None)
    text = daily_digest.get_or_build(db, today=date(2026, 7, 3))
    assert "1 560" in text or "1560" in text  # stats present
    assert len(text) > 0


def test_digest_rebuilds_on_new_day(db, monkeypatch):
    monkeypatch.setattr(daily_digest, "complete_with_fallback", lambda db_, s, u: "tip")
    a = daily_digest.get_or_build(db, today=date(2026, 7, 2))
    b = daily_digest.get_or_build(db, today=date(2026, 7, 4))
    assert db.query(Setting).filter(Setting.key == "digest.2026-07-04").first() is not None
