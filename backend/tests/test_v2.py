import pytest
from decimal import Decimal
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Category, Debt, MonthlyPlan, SinkingFund, Transaction
from app.services.allocation import (
    AllocationInput,
    allocate_income,
    get_allocation_buckets,
    get_unallocated_total,
)
from app.services.debts import compute_priority_ranks, debt_cost_analysis
from app.services.forecast import ForecastService
from app.services.sinking_funds import SinkingFundService
from app.seed import load_demo_data as seed_database


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    seed_database(session)
    yield session
    session.close()


def test_unallocated_zero_after_allocate(db):
    tx = Transaction(type="income", amount=Decimal("100000"), date=date.today())
    db.add(tx)
    db.commit()

    from app.services.allocation import get_allocation_buckets
    buckets = get_allocation_buckets(db, date.today().year, date.today().month, tx.amount)
    allocations = []
    assigned = Decimal("0")
    savings_cat_id = next(
        item.id for b in buckets if b.group == "savings" for item in b.items if item.kind == "category"
    )
    for b in buckets:
        for item in b.items:
            if item.suggested_amount > 0:
                allocations.append(AllocationInput(
                    category_id=item.id if item.kind == "category" else None,
                    fund_id=item.id if item.kind == "fund" else None,
                    amount=item.suggested_amount, group=item.group))
                assigned += item.suggested_amount
    # top up remainder into the savings category so the income is fully allocated
    remainder = tx.amount - assigned
    if remainder > 0:
        allocations.append(AllocationInput(category_id=savings_cat_id, amount=remainder, group="savings"))
    allocate_income(db, tx.id, allocations)
    db.refresh(tx)
    assert tx.is_fully_allocated


def test_allocation_three_buckets(db):
    plan = MonthlyPlan(year=date.today().year, month=date.today().month, expected_income=Decimal("110000"))
    db.add(plan)
    db.commit()

    buckets = get_allocation_buckets(db, date.today().year, date.today().month, Decimal("110000"))
    assert len(buckets) == 3
    groups = [b.group for b in buckets]
    assert groups == ["needs", "wants", "savings"]
    savings = next(b for b in buckets if b.group == "savings")
    assert any(item.kind == "category" for item in savings.items)


def test_sinking_fund_contribute_and_spend(db):
    fund = db.query(SinkingFund).first()
    SinkingFundService.contribute(db, fund.id, Decimal("5000"), date.today())
    db.refresh(fund)
    assert fund.current_amount == Decimal("5000")

    SinkingFundService.spend_from_fund(
        db, fund.id, Decimal("2000"), date.today(), None, None, "test"
    )
    db.refresh(fund)
    assert fund.current_amount == Decimal("3000")


def test_sinking_fund_rolling_reset(db):
    fund = SinkingFund(
        name="Test rolling",
        target_amount=Decimal("1000"),
        current_amount=Decimal("0"),
        monthly_contribution=Decimal("500"),
        group="wants",
        is_rolling=True,
    )
    db.add(fund)
    db.commit()
    SinkingFundService.contribute(db, fund.id, Decimal("1000"), date.today())
    db.refresh(fund)
    assert fund.current_amount == Decimal("0")


def test_forecast_three_months(db):
    forecast = ForecastService.cash_flow_forecast(db, 3)
    assert len(forecast) == 3
    assert all(f.income > 0 for f in forecast)


def test_debt_avalanche_priority(db):
    compute_priority_ranks(db)
    credit = db.query(Debt).filter(Debt.type == "credit_card").first()
    split = db.query(Debt).filter(Debt.type == "split").first()
    assert credit.priority_rank == 1
    assert split.priority_rank == 2


def test_debt_cost_analysis(db):
    credit = db.query(Debt).filter(Debt.type == "credit_card").first()
    analysis = debt_cost_analysis(db, credit.id)
    assert analysis is not None
    assert len(analysis.scenarios) >= 1
    assert analysis.scenarios[0].months_to_close > 0
