from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session, joinedload

from app.models import Category, Debt, DebtPayment, MonthlyPlan, Transaction
from app.seed import GROUP_PERCENTS


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
    def plan_vs_fact(db: Session, year: int, month: int) -> list[CategoryComparison]:
        plan = (
            db.query(MonthlyPlan)
            .options(joinedload(MonthlyPlan.limits))
            .filter(MonthlyPlan.year == year, MonthlyPlan.month == month)
            .first()
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
            if plan:
                lim = next((l for l in plan.limits if l.category_id == cat.id), None)
                if lim:
                    plan_amount = lim.limit_amount
                elif plan.expected_income > 0:
                    pct = GROUP_PERCENTS.get(cat.group, 0)
                    group_cats = [c for c in categories if c.group == cat.group]
                    if group_cats:
                        plan_amount = plan.expected_income * Decimal(pct) / Decimal("100") / len(group_cats)

            fact = (
                db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .filter(
                    Transaction.type == "expense",
                    Transaction.category_id == cat.id,
                    extract("year", Transaction.date) == year,
                    extract("month", Transaction.date) == month,
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
    def top_categories(db: Session, year: int, month: int, limit: int = 5) -> list[tuple[str, Decimal]]:
        rows = (
            db.query(Category.name, func.sum(Transaction.amount))
            .join(Transaction)
            .filter(
                Transaction.type == "expense",
                extract("year", Transaction.date) == year,
                extract("month", Transaction.date) == month,
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
    def debt_payments(db: Session, debt_id: int) -> list[DebtPayment]:
        return (
            db.query(DebtPayment)
            .filter(DebtPayment.debt_id == debt_id)
            .order_by(DebtPayment.date.desc())
            .all()
        )
