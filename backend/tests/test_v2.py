import pytest
from decimal import Decimal
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Debt, SinkingFund
from app.services.debts import compute_priority_ranks, debt_cost_analysis
from app.services.sinking_funds import SinkingFundService
from app.seed import load_demo_data as seed_database
from tests.conftest import WS, create_workspace


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    create_workspace(session)  # id == WS
    seed_database(session, WS)
    yield session
    session.close()


def test_sinking_fund_contribute_and_spend(db):
    fund = db.query(SinkingFund).first()
    SinkingFundService.contribute(db, WS, fund.id, Decimal("5000"), date.today())
    db.refresh(fund)
    assert fund.current_amount == Decimal("5000")

    SinkingFundService.spend_from_fund(
        db, WS, fund.id, Decimal("2000"), date.today(), None, None, "test"
    )
    db.refresh(fund)
    assert fund.current_amount == Decimal("3000")


def test_sinking_fund_rolling_reset(db):
    fund = SinkingFund(
        workspace_id=WS,
        name="Test rolling",
        target_amount=Decimal("1000"),
        current_amount=Decimal("0"),
        monthly_contribution=Decimal("500"),
        group="wants",
        is_rolling=True,
    )
    db.add(fund)
    db.commit()
    SinkingFundService.contribute(db, WS, fund.id, Decimal("1000"), date.today())
    db.refresh(fund)
    assert fund.current_amount == Decimal("0")


def test_debt_avalanche_priority(db):
    compute_priority_ranks(db, WS)
    credit = db.query(Debt).filter(Debt.type == "credit_card").first()
    split = db.query(Debt).filter(Debt.type == "split").first()
    assert credit.priority_rank == 1
    assert split.priority_rank == 2


def test_debt_cost_analysis(db):
    credit = db.query(Debt).filter(Debt.type == "credit_card").first()
    analysis = debt_cost_analysis(db, WS, credit.id)
    assert analysis is not None
    assert len(analysis.scenarios) >= 1
    assert analysis.scenarios[0].months_to_close > 0
