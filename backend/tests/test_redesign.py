from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers models with Base.metadata before create_all
from app.db import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_model_shape(db):
    import app.models as m

    # Goal is gone
    assert not hasattr(m, "Goal")
    assert not hasattr(m, "GoalContribution")

    # SinkingFund uses `group`, not `category_group`
    fund = m.SinkingFund(name="Отпуск", target_amount=Decimal("50000"), group="savings")
    db.add(fund)
    db.commit()
    assert fund.group == "savings"
    assert not hasattr(fund, "category_group")

    # DepositContribution exists
    c = m.DepositContribution(amount=Decimal("1000"), date=date.today(), source="manual")
    db.add(c)
    db.commit()
    assert c.id is not None

    # IncomeAllocation has to_deposit
    a = m.IncomeAllocation(income_tx_id=1, amount=Decimal("5"), allocation_level=4, to_deposit=True)
    assert a.to_deposit is True


from app.seed import load_demo_data, ensure_settings
from app.models import Category, SinkingFund, Setting


def test_seed_no_savings_categories_no_goals(db):
    ensure_settings(db)
    load_demo_data(db)

    groups = {c.group for c in db.query(Category).all()}
    assert "savings" not in groups
    assert groups <= {"needs", "wants", "income"}

    funds = db.query(SinkingFund).all()
    assert funds, "demo should create копилки"
    assert all(f.group in ("wants", "savings") for f in funds)
    assert any(f.group == "savings" for f in funds)

    assert db.query(Setting).filter(Setting.key == "deposit_monthly_target").first() is not None


from app.services.deposit import DepositService
from app.models import DepositContribution


def test_deposit_contribute_grows_balance(db):
    ensure_settings(db)
    start = DepositService.get_balance(db)
    new_balance = DepositService.contribute(db, Decimal("10000"), source="manual")
    assert new_balance == start + Decimal("10000")
    assert DepositService.get_balance(db) == start + Decimal("10000")
    assert db.query(DepositContribution).count() == 1


from app.models import Transaction, MonthlyPlan
from app.services.allocation import (
    get_allocation_buckets, allocate_income, AllocationInput, get_unallocated_for_tx,
)
from app.services.sinking_funds import SinkingFundService


def test_buckets_mirror_503020(db):
    ensure_settings(db); load_demo_data(db)
    y, mth = date.today().year, date.today().month
    buckets = get_allocation_buckets(db, y, mth, Decimal("100000"))
    groups = {b.group for b in buckets}
    assert groups == {"needs", "wants", "savings"}
    by = {b.group: b for b in buckets}
    assert by["needs"].percent == 50 and by["needs"].target_amount == Decimal("50000")
    assert by["wants"].percent == 30
    assert by["savings"].percent == 20
    # savings bucket includes the Вклад destination
    assert any(i.kind == "deposit" for i in by["savings"].items)


def test_allocate_to_deposit_grows_deposit(db):
    ensure_settings(db); load_demo_data(db)
    from app.services.deposit import DepositService
    tx = Transaction(type="income", amount=Decimal("20000"), date=date.today())
    db.add(tx); db.commit()
    before = DepositService.get_balance(db)
    allocate_income(db, tx.id, [AllocationInput(to_deposit=True, amount=Decimal("20000"), group="savings")])
    db.refresh(tx)
    assert tx.is_fully_allocated
    assert DepositService.get_balance(db) == before + Decimal("20000")
    assert get_unallocated_for_tx(db, tx) == Decimal("0")


def test_fund_create_and_spend_with_group(db):
    f = SinkingFundService.create(db, name="Отпуск", target_amount=Decimal("100000"),
                                  monthly_contribution=Decimal("8000"), group="wants")
    assert f.group == "wants"
    SinkingFundService.contribute(db, f.id, Decimal("8000"), date.today())
    tx = SinkingFundService.spend_from_fund(db, f.id, Decimal("3000"), date.today(),
                                            category_id=None, user_id=None, comment=None)
    db.refresh(f)
    assert f.current_amount == Decimal("5000")
    assert tx.is_sinking_fund_spend and tx.fund_id == f.id


def test_dashboard_savings_counts_deposit(db):
    ensure_settings(db); load_demo_data(db)
    from app.services.deposit import DepositService
    from app.services.dashboard import DashboardService
    y, mth = date.today().year, date.today().month
    db.add(Transaction(type="income", amount=Decimal("100000"), date=date.today())); db.commit()
    DepositService.contribute(db, Decimal("15000"), source="manual")

    s = DashboardService.get_month_summary(db, y, mth)
    sav = next(g for g in s.groups if g.name == "savings")
    assert sav.spent >= Decimal("15000")
    assert {g.name for g in s.groups} == {"needs", "wants", "savings"}
    assert not hasattr(s, "goals") or s.goals == []


def test_analytics_has_503020_split(db):
    ensure_settings(db); load_demo_data(db)
    from app.services.analytics import AnalyticsService
    y, mth = date.today().year, date.today().month
    data = AnalyticsService.split_503020(db, y, mth)
    assert set(data.keys()) == {"needs", "wants", "savings"}
    assert set(data["needs"].keys()) == {"fact", "ideal", "percent"}
