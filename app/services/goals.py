from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Goal, Transaction
from app.services.deposit_calc import build_forecast
from app.services.plan import DepositService


def sync_goal_from_transaction(db: Session, tx: Transaction) -> None:
    if tx.type not in ("expense", "transfer") or not tx.category_id:
        return
    goals = (
        db.query(Goal)
        .filter(Goal.is_active.is_(True), Goal.linked_category_id == tx.category_id)
        .all()
    )
    for goal in goals:
        goal.current_amount += tx.amount


def remove_goal_from_transaction(db: Session, tx: Transaction) -> None:
    if tx.type not in ("expense", "transfer") or not tx.category_id:
        return
    goals = (
        db.query(Goal)
        .filter(Goal.is_active.is_(True), Goal.linked_category_id == tx.category_id)
        .all()
    )
    for goal in goals:
        goal.current_amount -= tx.amount
        if goal.current_amount < 0:
            goal.current_amount = Decimal("0")


def months_to_goal_linear(goal: Goal) -> int | None:
    if goal.monthly_contribution <= 0 or goal.target_amount <= goal.current_amount:
        return None
    remaining = goal.target_amount - goal.current_amount
    return int((remaining / goal.monthly_contribution).to_integral_value())


def months_to_goal_with_capitalization(
    db: Session,
    goal: Goal,
    monthly_contribution: Decimal | None = None,
) -> int | None:
    if goal.name == "Машина" and goal.deadline:
        contrib = monthly_contribution or goal.monthly_contribution or Decimal("15000")
        rows = DepositService.forecast_forward(db, contrib, goal.deadline)
        if not rows:
            return None
        for i, row in enumerate(rows):
            if row.balance_after >= goal.target_amount:
                return i + 1
        return len(rows)
    return months_to_goal_linear(goal)


def cascade_goal_scenario(
    db: Session,
    goal: Goal,
    extra_monthly: Decimal,
) -> tuple[int | None, int | None]:
    """Returns (months at current contrib, months at increased contrib)."""
    current = months_to_goal_with_capitalization(db, goal, goal.monthly_contribution)
    increased = months_to_goal_with_capitalization(
        db, goal, goal.monthly_contribution + extra_monthly
    )
    return current, increased


def goal_forecast_rows(
    db: Session,
    goal: Goal,
    monthly_contribution: Decimal,
    months: int = 12,
) -> list[tuple[date, Decimal]]:
    if goal.name == "Машина" and goal.deadline:
        s = DepositService.get_settings(db)
        start = date.today()
        end = goal.deadline
        rows = build_forecast(
            start,
            s["balance"],
            s["rate"],
            end,
            monthly_contribution,
            rate_schedule=s["rate_schedule"],
            capitalization_day=s["cap_day"],
        )
        return [(r.date, r.balance_after) for r in rows[:months]]
    balance = goal.current_amount
    result = []
    y, m = date.today().year, date.today().month
    for _ in range(months):
        balance += monthly_contribution
        result.append((date(y, m, 1), balance))
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return result
