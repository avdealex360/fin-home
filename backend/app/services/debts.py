from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Debt


@dataclass
class DebtCostScenario:
    monthly_payment: Decimal
    months_to_close: int
    total_interest: Decimal
    label: str


@dataclass
class DebtCostAnalysis:
    debt_id: int
    name: str
    remaining: Decimal
    interest_rate: Decimal
    scenarios: list[DebtCostScenario]


def compute_priority_ranks(db: Session, ws_id: int) -> None:
    debts = (
        db.query(Debt)
        .filter(Debt.workspace_id == ws_id, Debt.is_closed.is_(False))
        .order_by(Debt.interest_rate.desc(), Debt.remaining.asc())
        .all()
    )
    for rank, debt in enumerate(debts, start=1):
        debt.priority_rank = rank
    db.commit()


def get_active_debts_sorted(db: Session, ws_id: int) -> list[Debt]:
    compute_priority_ranks(db, ws_id)
    debts = db.query(Debt).filter(Debt.workspace_id == ws_id, Debt.is_closed.is_(False)).all()
    debts.sort(key=lambda d: (-float(d.interest_rate), d.remaining))
    return debts


def _months_with_interest(
    remaining: Decimal,
    annual_rate: Decimal,
    monthly_payment: Decimal,
) -> tuple[int, Decimal]:
    if monthly_payment <= 0 or remaining <= 0:
        return 0, Decimal("0")
    balance = remaining
    monthly_rate = annual_rate / Decimal("100") / Decimal("12")
    total_interest = Decimal("0")
    months = 0
    max_months = 600
    while balance > Decimal("0.01") and months < max_months:
        interest = (balance * monthly_rate).quantize(Decimal("0.01"))
        total_interest += interest
        balance = balance + interest - monthly_payment
        months += 1
        if balance <= 0:
            balance = Decimal("0")
    return months, total_interest


def debt_cost_analysis(db: Session, ws_id: int, debt_id: int) -> DebtCostAnalysis | None:
    debt = db.query(Debt).filter(Debt.id == debt_id, Debt.workspace_id == ws_id).first()
    if not debt or debt.is_closed:
        return None

    scenarios = []
    min_payment = debt.monthly_payment
    if min_payment > 0:
        months, interest = _months_with_interest(debt.remaining, debt.interest_rate, min_payment)
        scenarios.append(
            DebtCostScenario(
                monthly_payment=min_payment,
                months_to_close=months,
                total_interest=interest,
                label="Минимальный платёж",
            )
        )
        double = min_payment * 2
        months2, interest2 = _months_with_interest(debt.remaining, debt.interest_rate, double)
        scenarios.append(
            DebtCostScenario(
                monthly_payment=double,
                months_to_close=months2,
                total_interest=interest2,
                label="Удвоенный платёж",
            )
        )

    return DebtCostAnalysis(
        debt_id=debt.id,
        name=debt.name,
        remaining=debt.remaining,
        interest_rate=debt.interest_rate,
        scenarios=scenarios,
    )


def monthly_interest_cost(debt: Debt) -> Decimal:
    if debt.interest_rate <= 0 or debt.remaining <= 0:
        return Decimal("0")
    return (debt.remaining * debt.interest_rate / Decimal("1200")).quantize(Decimal("0.01"))
