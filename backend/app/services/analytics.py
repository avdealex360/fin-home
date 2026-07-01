from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, extract, func, or_
from sqlalchemy.orm import Session, joinedload

from app.models import Category, Debt, DebtPayment, MonthlyPlan, Transaction
from app.seed import GROUP_PERCENTS
from app.util import months_in_range


@dataclass
class CategoryComparison:
    category_id: int
    category_name: str
    group: str
    plan: Decimal
    fact: Decimal
    diff: Decimal
    diff_percent: float


@dataclass
class MonthlyTrend:
    year: int
    month: int
    income: Decimal
    expense: Decimal
    savings: Decimal


class AnalyticsService:
    @staticmethod
    def plan_vs_fact(db: Session, start: date, end: date) -> list[CategoryComparison]:
        month_pairs = months_in_range(start, end)
        plans = (
            db.query(MonthlyPlan)
            .options(joinedload(MonthlyPlan.limits))
            .filter(or_(*(and_(MonthlyPlan.year == y, MonthlyPlan.month == m) for y, m in month_pairs)))
            .all()
        )
        categories = (
            db.query(Category)
            .filter(Category.is_hidden.is_(False))
            .order_by(Category.sort_order)
            .all()
        )
        results = []
        for cat in categories:
            plan_amount = Decimal("0")
            for plan in plans:
                lim = next((l for l in plan.limits if l.category_id == cat.id), None)
                if lim:
                    plan_amount += lim.limit_amount
                elif plan.expected_income > 0:
                    pct = GROUP_PERCENTS.get(cat.group, 0)
                    group_cats = [c for c in categories if c.group == cat.group]
                    if group_cats:
                        plan_amount += plan.expected_income * Decimal(pct) / Decimal("100") / len(group_cats)

            fact = (
                db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .filter(
                    Transaction.type == "expense",
                    Transaction.category_id == cat.id,
                    Transaction.date.between(start, end),
                )
                .scalar()
            ) or Decimal("0")

            diff = fact - plan_amount
            diff_pct = float(diff / plan_amount * 100) if plan_amount > 0 else 0.0
            results.append(
                CategoryComparison(
                    category_id=cat.id,
                    category_name=cat.name,
                    group=cat.group,
                    plan=plan_amount,
                    fact=fact,
                    diff=diff,
                    diff_percent=diff_pct,
                )
            )
        return results

    @staticmethod
    def monthly_trends(db: Session, months: int = 12) -> list[MonthlyTrend]:
        today = date.today()
        trends = []
        y, m = today.year, today.month
        for _ in range(months):
            income = (
                db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .filter(
                    Transaction.type == "income",
                    extract("year", Transaction.date) == y,
                    extract("month", Transaction.date) == m,
                )
                .scalar()
            ) or Decimal("0")
            expense = (
                db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .filter(
                    Transaction.type == "expense",
                    extract("year", Transaction.date) == y,
                    extract("month", Transaction.date) == m,
                )
                .scalar()
            ) or Decimal("0")
            savings = (
                db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .join(Category)
                .filter(
                    Transaction.type.in_(["expense", "transfer"]),
                    Category.group == "savings",
                    extract("year", Transaction.date) == y,
                    extract("month", Transaction.date) == m,
                )
                .scalar()
            ) or Decimal("0")
            trends.append(MonthlyTrend(year=y, month=m, income=income, expense=expense, savings=savings))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        trends.reverse()
        return trends

    @staticmethod
    def top_categories(db: Session, start: date, end: date, limit: int = 5) -> list[tuple[str, Decimal]]:
        rows = (
            db.query(Category.name, func.sum(Transaction.amount))
            .join(Transaction)
            .filter(
                Transaction.type == "expense",
                Transaction.date.between(start, end),
            )
            .group_by(Category.name)
            .order_by(func.sum(Transaction.amount).desc())
            .limit(limit)
            .all()
        )
        return [(name, amount or Decimal("0")) for name, amount in rows]

    @staticmethod
    def category_history(db: Session, category_id: int, months: int = 6) -> list[tuple[int, int, Decimal]]:
        today = date.today()
        y, m = today.year, today.month
        history = []
        for _ in range(months):
            total = (
                db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .filter(
                    Transaction.type == "expense",
                    Transaction.category_id == category_id,
                    extract("year", Transaction.date) == y,
                    extract("month", Transaction.date) == m,
                )
                .scalar()
            ) or Decimal("0")
            history.append((y, m, total))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        history.reverse()
        return history

    @staticmethod
    def debt_forecast(db: Session, debt_id: int) -> date | None:
        debt = db.query(Debt).filter(Debt.id == debt_id).first()
        if not debt or debt.monthly_payment <= 0 or debt.remaining <= 0:
            return None
        months = int((debt.remaining / debt.monthly_payment).to_integral_value()) + 1
        today = date.today()
        y, m = today.year, today.month + months
        while m > 12:
            m -= 12
            y += 1
        return date(y, m, 1)

    @staticmethod
    def cumulative_trends(db: Session, months: int = 12) -> list[dict]:
        trends = AnalyticsService.monthly_trends(db, months)
        cum_income = Decimal("0")
        cum_expense = Decimal("0")
        cum_savings = Decimal("0")
        result = []
        for t in trends:
            cum_income += t.income
            cum_expense += t.expense
            cum_savings += t.savings
            result.append(
                {
                    "label": f"{t.year}-{t.month:02d}",
                    "income": float(cum_income),
                    "expense": float(cum_expense),
                    "savings": float(cum_savings),
                }
            )
        return result

    @staticmethod
    def category_average(db: Session, category_id: int, months: int = 6) -> Decimal:
        history = AnalyticsService.category_history(db, category_id, months)
        if not history:
            return Decimal("0")
        total = sum(amount for _, _, amount in history)
        return (total / len(history)).quantize(Decimal("0.01"))

    @staticmethod
    def debt_payments(db: Session, debt_id: int) -> list[DebtPayment]:
        return (
            db.query(DebtPayment)
            .filter(DebtPayment.debt_id == debt_id)
            .order_by(DebtPayment.date.desc())
            .all()
        )

    @staticmethod
    def split_503020(db: Session, start: date, end: date) -> dict:
        from decimal import Decimal
        from app.models import Category, Transaction
        from app.services.dashboard import _savings_fund_contributions

        def expense_for(group: str) -> Decimal:
            return Decimal(str((
                db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .join(Category, Category.id == Transaction.category_id)
                .filter(Transaction.type == "expense", Category.group == group,
                        Transaction.date.between(start, end))
                .scalar()
            ) or "0"))

        income = Decimal(str((
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(Transaction.type == "income", Transaction.date.between(start, end))
            .scalar()
        ) or "0"))

        needs, wants = expense_for("needs"), expense_for("wants")
        fund_contrib = sum(
            (_savings_fund_contributions(db, y, m) for y, m in months_in_range(start, end)),
            Decimal("0"),
        )
        savings = expense_for("savings") + fund_contrib
        total = (needs + wants + savings) or Decimal("1")
        out = {}
        for name, fact, pct in (("needs", needs, 50), ("wants", wants, 30), ("savings", savings, 20)):
            out[name] = {
                "fact": float(fact),
                "ideal": float(income * Decimal(pct) / Decimal("100")),
                "percent": float(fact / total * 100),
            }
        return out
