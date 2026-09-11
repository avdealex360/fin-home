"""History-based month outlook (services/outlook.py + /api/analytics/outlook)."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Category, Transaction
from app.services.outlook import OutlookService
from tests.conftest import create_workspace


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _seed(db, ws_id):
    rent = Category(workspace_id=ws_id, name="Аренда", group="needs", sort_order=1)
    food = Category(workspace_id=ws_id, name="Продукты", group="needs", sort_order=2)
    vet = Category(workspace_id=ws_id, name="Ветеринар", group="needs", sort_order=3)
    save = Category(workspace_id=ws_id, name="Подушка", group="savings", sort_order=4)
    db.add_all([rent, food, vet, save])
    db.flush()

    def tx(cat, amount, d):
        db.add(Transaction(workspace_id=ws_id, type="expense", amount=Decimal(amount), date=d, category_id=cat.id))

    # July + August history: rent on the 15th, food spread, vet lumpy.
    for m in (7, 8):
        tx(rent, "50000", date(2026, m, 15))
        for day in (2, 9, 16, 23):
            tx(food, "5000", date(2026, m, day))
        tx(save, "20000", date(2026, m, 5))
    tx(vet, "40000", date(2026, 7, 21))
    tx(vet, "5000", date(2026, 8, 15))
    # September so far (viewed at the 11th): only food, rent not paid yet.
    tx(food, "5000", date(2026, 9, 2))
    tx(food, "5000", date(2026, 9, 9))
    db.commit()
    return rent, food, vet


def test_expected_remaining_projects_unpaid_regulars_not_lumps(db):
    ws = create_workspace(db)
    rent, food, vet = _seed(db, ws.id)
    o = OutlookService.month_outlook(db, ws.id, 2026, 9, today=date(2026, 9, 11))

    assert o.history_months == 2
    assert o.day == 11 and o.days_left == 19
    assert o.spent == Decimal("10000")
    assert o.spent_savings == Decimal("0")  # savings never count as spend

    by = {c.name: c for c in o.categories}
    assert by["Аренда"].kind == "regular"
    assert by["Аренда"].remaining_typical == Decimal("50000")  # not paid yet → still to come
    assert by["Продукты"].remaining_typical == Decimal("10000")  # 20 000 typical − 10 000 spent
    assert by["Ветеринар"].kind == "variable"
    assert by["Ветеринар"].typical == Decimal("5000")  # floor, not the surgery
    assert o.expected_remaining == Decimal("65000")
    assert o.forecast_total == Decimal("75000")
    # Median of 11 elapsed days: two days with 5000, nine with 0 → 0.
    assert o.median_day == Decimal("0")
    # Previous month by the 11th: two food charges (2nd, 9th); savings excluded.
    assert o.prev_same_day == Decimal("10000")
    assert o.prev_month_total == Decimal("75000")
    assert len(o.prev_cumulative) == 31


def test_past_month_has_nothing_left_to_come(db):
    ws = create_workspace(db)
    _seed(db, ws.id)
    o = OutlookService.month_outlook(db, ws.id, 2026, 8, today=date(2026, 9, 11))
    assert o.days_left == 0
    assert o.expected_remaining == Decimal("0")
    assert o.forecast_total == o.spent == Decimal("75000")


def test_no_history_falls_back_to_limits_and_skips_oneoffs(db):
    ws = create_workspace(db)
    _seed(db, ws.id)
    o = OutlookService.month_outlook(db, ws.id, 2026, 7, today=date(2026, 7, 20))
    assert o.history_months == 0
    assert all(c.kind == "new" for c in o.categories)
    assert o.oneoffs == []  # rent must not be reported as a spike without history
    assert o.prev_same_day is None


def test_outlook_endpoint(api):
    with api.Session() as s:
        _seed(s, api.ws_id)
    r = api.client.get("/api/analytics/outlook?year=2026&month=9")
    assert r.status_code == 200
    body = r.json()
    assert body["history_months"] == 2
    assert body["forecast_total"] >= body["spent"]
    assert {c["kind"] for c in body["categories"]} <= {"regular", "variable", "new"}
