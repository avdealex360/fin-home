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
