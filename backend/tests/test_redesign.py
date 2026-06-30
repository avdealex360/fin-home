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


from app.services.sinking_funds import SinkingFundService


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
