from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AppUser, Category, Transaction
from app.services.ai.base import ParsedEntry
from app.services import tx_resolver


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add_all([
        Category(name="Продукты и быт", group="needs", sort_order=1),
        Category(name="Кофе", group="wants", sort_order=2),
        AppUser(name="Леша", telegram_id="111"),
        AppUser(name="Катя", telegram_id="222"),
        AppUser(name="Общий"),
    ])
    s.commit()
    yield s
    s.close()


def test_resolve_category_exact_and_substring(db):
    assert tx_resolver.resolve_category_id(db, "Кофе") is not None
    # substring / case-insensitive
    assert tx_resolver.resolve_category_id(db, "продукты") is not None
    assert tx_resolver.resolve_category_id(db, "Ракета") is None
    assert tx_resolver.resolve_category_id(db, None) is None


def test_resolve_user_defaults_to_sender(db):
    sender = db.query(AppUser).filter_by(name="Леша").first()
    assert tx_resolver.resolve_user_id(db, None, sender) == sender.id
    katya = db.query(AppUser).filter_by(name="Катя").first()
    assert tx_resolver.resolve_user_id(db, "Катя", sender) == katya.id


def test_create_transactions_writes_and_marks_unresolved(db):
    sender = db.query(AppUser).filter_by(name="Леша").first()
    entries = [
        ParsedEntry(Decimal("1560"), "expense", "Продукты и быт", None, None, "магазин", "high"),
        ParsedEntry(Decimal("999"), "expense", "Несуществующая", None, None, None, "low"),
    ]
    txs = tx_resolver.create_transactions(db, entries, sender)
    assert len(txs) == 2
    assert txs[0].category_id is not None and txs[0].user_id == sender.id
    assert txs[0].date == date.today()
    assert txs[1].category_id is None
    assert "Несуществующая" in (txs[1].comment or "")
    assert db.query(Transaction).count() == 2
