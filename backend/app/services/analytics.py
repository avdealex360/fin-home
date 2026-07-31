from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session, joinedload

from app.models import Category, MonthlyPlan, Transaction
from app.util import months_in_range, shift_month


@dataclass
class CategoryComparison:
    category_id: int
    category_name: str
    group: str
    plan: Decimal
    fact: Decimal
    diff: Decimal
    diff_percent: float
    # Trailing-3-months context (window right before the period start):
    months_active: int  # in how many of those months the category had spend
    avg3: Decimal  # average monthly spend over that window


@dataclass
class MonthlyTrend:
    year: int
    month: int
    income: Decimal
    expense: Decimal
    savings: Decimal


class AnalyticsService:
    @staticmethod
    def plan_vs_fact(db: Session, ws_id: int, start: date, end: date) -> list[CategoryComparison]:
        month_pairs = months_in_range(start, end)
        plans = (
            db.query(MonthlyPlan)
            .filter(
                MonthlyPlan.workspace_id == ws_id,
                MonthlyPlan.year.in_({y for y, _ in month_pairs}),
            )
            .options(joinedload(MonthlyPlan.limits))
            .all()
        )
        plans = [p for p in plans if (p.year, p.month) in set(month_pairs)]
        categories = (
            db.query(Category)
            .filter(Category.workspace_id == ws_id, Category.is_hidden.is_(False))
            .order_by(Category.sort_order)
            .all()
        )

        # One grouped query for the facts of the whole period.
        facts = dict(
            db.query(Transaction.category_id, func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.workspace_id == ws_id,
                Transaction.type == "expense",
                Transaction.category_id.isnot(None),
                Transaction.date.between(start, end),
            )
            .group_by(Transaction.category_id)
            .all()
        )

        # Trailing 3 months before the period: months with spend + average.
        hist_start_y, hist_start_m = shift_month(start.year, start.month, -3)
        hist_start = date(hist_start_y, hist_start_m, 1)
        hist_end = start - timedelta(days=1)
        history = (
            db.query(
                Transaction.category_id,
                func.count(func.distinct(
                    extract("year", Transaction.date) * 12 + extract("month", Transaction.date)
                )),
                func.coalesce(func.sum(Transaction.amount), 0),
            )
            .filter(
                Transaction.workspace_id == ws_id,
                Transaction.type == "expense",
                Transaction.category_id.isnot(None),
                Transaction.date.between(hist_start, hist_end),
            )
            .group_by(Transaction.category_id)
            .all()
        )
        hist_by_cat = {cat_id: (int(months), Decimal(total)) for cat_id, months, total in history}

        results = []
        for cat in categories:
            # Plan is the explicitly configured limits only. Synthesizing a
            # "plan" by evenly splitting expected income across a group read
            # as noise next to real limits — an unplanned category is plan 0.
            plan_amount = sum(
                (lim.limit_amount for plan in plans for lim in plan.limits if lim.category_id == cat.id),
                Decimal("0"),
            )
            fact = Decimal(facts.get(cat.id, 0))
            months_active, hist_total = hist_by_cat.get(cat.id, (0, Decimal("0")))
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
                    months_active=months_active,
                    avg3=(hist_total / 3).quantize(Decimal("0.01")),
                )
            )
        return results

    @staticmethod
    def monthly_trends(
        db: Session, ws_id: int, months: int = 12, anchor: tuple[int, int] | None = None
    ) -> list[MonthlyTrend]:
        """`months` trailing months ending at `anchor` (defaults to current month).

        Anchoring on the period selected in the UI means navigating between
        months actually moves the trend window, so the chart reflects the view.
        """
        if anchor:
            end_y, end_m = anchor
        else:
            today = date.today()
            end_y, end_m = today.year, today.month
        start_y, start_m = shift_month(end_y, end_m, -(months - 1))
        start = date(start_y, start_m, 1)
        from calendar import monthrange

        end = date(end_y, end_m, monthrange(end_y, end_m)[1])

        ym = (extract("year", Transaction.date), extract("month", Transaction.date))

        def grouped(query_filter) -> dict[tuple[int, int], Decimal]:
            rows = (
                db.query(*ym, func.coalesce(func.sum(Transaction.amount), 0))
                .filter(
                    Transaction.workspace_id == ws_id,
                    Transaction.date.between(start, end),
                    *query_filter,
                )
                .group_by(*ym)
                .all()
            )
            return {(int(y), int(m)): Decimal(s) for y, m, s in rows}

        incomes = grouped([Transaction.type == "income"])
        expenses = grouped([Transaction.type == "expense"])
        savings_rows = (
            db.query(*ym, func.coalesce(func.sum(Transaction.amount), 0))
            .join(Category, Category.id == Transaction.category_id)
            .filter(
                Transaction.workspace_id == ws_id,
                Transaction.type.in_(["expense", "transfer"]),
                Category.group == "savings",
                Transaction.date.between(start, end),
            )
            .group_by(*ym)
            .all()
        )
        savings = {(int(y), int(m)): Decimal(s) for y, m, s in savings_rows}

        trends = []
        y, m = start_y, start_m
        for _ in range(months):
            trends.append(
                MonthlyTrend(
                    year=y,
                    month=m,
                    income=incomes.get((y, m), Decimal("0")),
                    expense=expenses.get((y, m), Decimal("0")),
                    savings=savings.get((y, m), Decimal("0")),
                )
            )
            y, m = shift_month(y, m, 1)
        return trends

    @staticmethod
    def top_categories(db: Session, ws_id: int, start: date, end: date, limit: int = 5) -> list[tuple[str, Decimal]]:
        rows = (
            db.query(Category.name, func.sum(Transaction.amount))
            .join(Transaction)
            .filter(
                Transaction.workspace_id == ws_id,
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
    def expense_total(db: Session, ws_id: int, start: date, end: date) -> Decimal:
        return Decimal(
            (
                db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .filter(
                    Transaction.workspace_id == ws_id,
                    Transaction.type == "expense",
                    Transaction.date.between(start, end),
                )
                .scalar()
            )
            or 0
        )
