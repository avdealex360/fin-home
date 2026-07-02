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


def test_resolve_category_uppercase_cyrillic(db):
    # SQLite's lower()/ilike don't fold Cyrillic case — this guards the Python-level fix.
    assert tx_resolver.resolve_category_id(db, "КОФЕ") is not None
    assert tx_resolver.resolve_category_id(db, "ПРОДУКТЫ") is not None


def test_resolve_user_uppercase_keyword_common(db):
    sender = db.query(AppUser).filter_by(name="Леша").first()
    common = db.query(AppUser).filter_by(name="Общий").first()
    assert tx_resolver.resolve_user_id(db, "ОБЩЕЕ", sender) == common.id


def test_resolve_category_yandex_group_suffix(db):
    db.add(Category(name="Квартира и жилье", group="needs", sort_order=10))
    db.commit()
    assert tx_resolver.resolve_category_id(db, "Квартира и жилье (needs)") is not None


def test_create_transactions_fills_comment_from_source_when_ai_omits(db):
    sender = db.query(AppUser).filter_by(name="Леша").first()
    source = "Ремонт бойлера 1840 Табачки для кальяна 3037"
    entries = [
        ParsedEntry(Decimal("1840"), "expense", "Продукты и быт", None, None, None, "high"),
        ParsedEntry(Decimal("3037"), "expense", "Кофе", None, None, None, "high"),
    ]
    txs = tx_resolver.create_transactions(db, entries, sender, source_text=source)
    assert txs[0].comment == "Ремонт бойлера"
    assert txs[1].comment == "Табачки для кальяна"


def test_resolve_category_group_token_with_source_hint(db):
    """GigaChat sometimes returns needs/wants instead of category names."""
    db.add_all([
        Category(name="Квартира и жилье", group="needs", sort_order=10),
        Category(name="Рестораны и доставка", group="wants", sort_order=11),
        Category(name="Связь и интернет", group="needs", sort_order=12),
    ])
    db.commit()
    source = "Ремонт бойлера 1840 Табачки для кальяна 3037, Яндекс облако 500"
    sender = db.query(AppUser).filter_by(name="Леша").first()
    entries = [
        ParsedEntry(Decimal("1840"), "expense", "needs", "Общий", None, None, "high"),
        ParsedEntry(Decimal("3037"), "expense", "wants", "Леша", None, None, "high"),
        ParsedEntry(Decimal("500"), "expense", "needs", "Общий", None, "Яндекс облако", "high"),
    ]
    txs = tx_resolver.create_transactions(db, entries, sender, source_text=source)
    names = {db.get(Category, t.category_id).name for t in txs if t.category_id}
    assert "Квартира и жилье" in names
    assert "Рестораны и доставка" in names
    assert "Связь и интернет" in names
