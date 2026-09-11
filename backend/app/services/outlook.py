"""Month outlook: what is still likely to be spent, based on the family's own
history rather than a straight-line "spent / day × days" projection.

Why: fixed payments (rent, utilities, debt instalments) land on one day and a
single big purchase (vet surgery, a freezer) is not going to repeat — dividing
the month-to-date total by the day number therefore says nothing useful. The
household already produces a better signal for free: how much each category
usually costs per month. This module turns that into

* ``typical`` per category — median monthly spend over the last ≤3 months
  that have data (mean when only two months exist);
* ``expected_remaining`` — Σ max(0, typical − spent so far), i.e. money that
  will most likely still leave this month (unpaid rent, groceries for the
  rest of the month, …), while an already-blown category adds nothing;
* ``forecast_total`` = spent + expected_remaining;
* ``median_day`` — median of daily totals over elapsed days (robust to lumps);
* previous month's cumulative curve and the "same day" comparison;
* one-off spikes: big charges in categories that are not regular.

Savings-group categories are transfers to yourself and are reported
separately: they never inflate the spend forecast.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from sqlalchemy import extract, func
from sqlalchemy.orm import Session, joinedload

from app.models import Category, MonthlyPlan, Transaction
from app.util import shift_month

HISTORY_MONTHS = 3
SPIKE_FACTOR = Decimal("2.5")
# A category with month-to-month spend spread wider than this is "variable"
# even though it shows up every month (vet bills, travel).
REGULAR_MAX_RATIO = Decimal("3")
SPEND_GROUPS = ("needs", "wants")

ZERO = Decimal("0")


@dataclass
class CategoryOutlook:
    category_id: int
    name: str
    group: str
    spent: Decimal
    typical: Decimal
    remaining_typical: Decimal
    # regular — present in every history month with a stable amount;
    # variable — present but lumpy or intermittent; new — no history at all.
    kind: str
    months_active: int


@dataclass
class OneOff:
    id: int
    date: date
    amount: Decimal
    category_name: str | None
    comment: str | None


@dataclass
class MonthOutlook:
    year: int
    month: int
    day: int
    days_in_month: int
    days_left: int
    # How many of the preceding ≤3 months carry any expense at all.
    history_months: int
    spent: Decimal
    spent_savings: Decimal
    typical_total: Decimal
    expected_remaining: Decimal
    forecast_total: Decimal
    median_day: Decimal
    median_cheque: Decimal
    prev_month_total: Decimal | None
    prev_same_day: Decimal | None
    prev_cumulative: list[Decimal] = field(default_factory=list)
    oneoffs: list[OneOff] = field(default_factory=list)
    oneoffs_total: Decimal = ZERO
    categories: list[CategoryOutlook] = field(default_factory=list)


def _elapsed_day(year: int, month: int, today: date) -> int:
    """Day of the viewed month that counts as 'now': today for the current
    month, the last day for a past month, 0 for a future one."""
    dim = monthrange(year, month)[1]
    if (year, month) == (today.year, today.month):
        return min(today.day, dim)
    if (year, month) < (today.year, today.month):
        return dim
    return 0


class OutlookService:
    @staticmethod
    def month_outlook(db: Session, ws_id: int, year: int, month: int, today: date | None = None) -> MonthOutlook:
        today = today or date.today()
        dim = monthrange(year, month)[1]
        day = _elapsed_day(year, month, today)
        days_left = dim - day

        categories = (
            db.query(Category)
            .filter(Category.workspace_id == ws_id, Category.is_hidden.is_(False))
            .order_by(Category.sort_order)
            .all()
        )
        group_of = {c.id: c.group for c in categories}

        # ── This month ─────────────────────────────────────────────────
        month_txs = (
            db.query(Transaction)
            .filter(
                Transaction.workspace_id == ws_id,
                Transaction.type == "expense",
                extract("year", Transaction.date) == year,
                extract("month", Transaction.date) == month,
            )
            .all()
        )
        spent_by_cat: dict[int, Decimal] = {}
        daily = [ZERO] * dim
        spent = ZERO
        spent_savings = ZERO
        spend_amounts: list[Decimal] = []
        for t in month_txs:
            grp = group_of.get(t.category_id or -1, "wants")
            if grp == "savings":
                spent_savings += t.amount
                continue
            spent += t.amount
            spend_amounts.append(t.amount)
            if t.category_id is not None:
                spent_by_cat[t.category_id] = spent_by_cat.get(t.category_id, ZERO) + t.amount
            if 1 <= t.date.day <= dim:
                daily[t.date.day - 1] += t.amount

        # ── History: per category per month, last ≤3 months before the view ──
        hist_y, hist_m = shift_month(year, month, -HISTORY_MONTHS)
        hist_start = date(hist_y, hist_m, 1)
        hist_end = date(year, month, 1) - timedelta(days=1)
        rows = (
            db.query(
                Transaction.category_id,
                extract("year", Transaction.date),
                extract("month", Transaction.date),
                func.coalesce(func.sum(Transaction.amount), 0),
            )
            .filter(
                Transaction.workspace_id == ws_id,
                Transaction.type == "expense",
                Transaction.date.between(hist_start, hist_end),
            )
            .group_by(Transaction.category_id, extract("year", Transaction.date), extract("month", Transaction.date))
            .all()
        )
        months_with_data: set[tuple[int, int]] = set()
        hist: dict[int, dict[tuple[int, int], Decimal]] = {}
        for cat_id, y, m, total in rows:
            key = (int(y), int(m))
            months_with_data.add(key)
            if cat_id is None:
                continue
            hist.setdefault(cat_id, {})[key] = Decimal(total)
        history_months = len(months_with_data)

        # No history yet → fall back to this month's limits as "typical".
        limits: dict[int, Decimal] = {}
        if history_months == 0:
            plan = (
                db.query(MonthlyPlan)
                .options(joinedload(MonthlyPlan.limits))
                .filter(MonthlyPlan.workspace_id == ws_id, MonthlyPlan.year == year, MonthlyPlan.month == month)
                .first()
            )
            if plan:
                limits = {lim.category_id: lim.limit_amount for lim in plan.limits}

        cat_out: list[CategoryOutlook] = []
        typical_total = ZERO
        expected_remaining = ZERO
        for c in categories:
            if c.group not in SPEND_GROUPS:
                continue
            c_spent = spent_by_cat.get(c.id, ZERO)
            per_month = hist.get(c.id, {})
            months_active = len(per_month)
            if history_months:
                series = [per_month.get(k, ZERO) for k in months_with_data]
                if months_active == 0:
                    kind = "new"
                elif months_active == history_months and (
                    history_months == 1 or min(series) > 0 and max(series) / min(series) <= REGULAR_MAX_RATIO
                ):
                    kind = "regular"
                else:
                    kind = "variable"
                # Regular: the usual amount. Variable/lumpy: only the floor that
                # showed up every time — a vet surgery must not be projected forward.
                typical = Decimal(median(series)) if kind == "regular" else Decimal(min(series))
            else:
                typical = limits.get(c.id, ZERO)
                kind = "new"
            remaining = max(typical - c_spent, ZERO)
            typical_total += typical
            expected_remaining += remaining
            cat_out.append(
                CategoryOutlook(
                    category_id=c.id,
                    name=c.name,
                    group=c.group,
                    spent=c_spent,
                    typical=typical.quantize(Decimal("1")),
                    remaining_typical=remaining.quantize(Decimal("1")),
                    kind=kind,
                    months_active=months_active,
                )
            )
        # Nothing left to come once the month is over.
        if days_left == 0:
            expected_remaining = ZERO

        elapsed = daily[:day]
        median_day = Decimal(median(elapsed)) if elapsed else ZERO
        median_cheque = Decimal(median(spend_amounts)) if spend_amounts else ZERO

        # ── Previous month's curve ─────────────────────────────────────
        py, pm = shift_month(year, month, -1)
        pdim = monthrange(py, pm)[1]
        prev_daily = [ZERO] * pdim
        prev_rows = (
            db.query(Transaction.date, Transaction.category_id, Transaction.amount)
            .filter(
                Transaction.workspace_id == ws_id,
                Transaction.type == "expense",
                extract("year", Transaction.date) == py,
                extract("month", Transaction.date) == pm,
            )
            .all()
        )
        for d, cat_id, amount in prev_rows:
            if group_of.get(cat_id or -1, "wants") == "savings":
                continue
            prev_daily[d.day - 1] += amount
        prev_cumulative: list[Decimal] = []
        acc = ZERO
        for v in prev_daily:
            acc += v
            prev_cumulative.append(acc)
        has_prev = bool(prev_rows)
        prev_month_total = prev_cumulative[-1] if has_prev else None
        prev_same_day = prev_cumulative[min(day, pdim) - 1] if has_prev and day > 0 else (ZERO if has_prev else None)

        # ── One-offs: big cheques outside regular categories ───────────
        regular_ids = {c.category_id for c in cat_out if c.kind == "regular"}
        oneoffs: list[OneOff] = []
        # Without history every category is "new", so rent would look like a spike — skip.
        if history_months and len(spend_amounts) >= 7 and median_cheque > 0:
            threshold = median_cheque * SPIKE_FACTOR
            for t in month_txs:
                if t.category_id in regular_ids or group_of.get(t.category_id or -1) == "savings":
                    continue
                if t.amount > threshold:
                    cat_name = next((c.name for c in categories if c.id == t.category_id), None)
                    oneoffs.append(OneOff(id=t.id, date=t.date, amount=t.amount, category_name=cat_name, comment=t.comment))
            oneoffs.sort(key=lambda o: o.amount, reverse=True)
        oneoffs_total = sum((o.amount for o in oneoffs), ZERO)

        return MonthOutlook(
            year=year,
            month=month,
            day=day,
            days_in_month=dim,
            days_left=days_left,
            history_months=history_months,
            spent=spent,
            spent_savings=spent_savings,
            typical_total=typical_total.quantize(Decimal("1")),
            expected_remaining=expected_remaining.quantize(Decimal("1")),
            forecast_total=(spent + expected_remaining).quantize(Decimal("1")),
            median_day=median_day.quantize(Decimal("1")),
            median_cheque=median_cheque.quantize(Decimal("1")),
            prev_month_total=prev_month_total,
            prev_same_day=prev_same_day,
            prev_cumulative=prev_cumulative,
            oneoffs=oneoffs[:5],
            oneoffs_total=oneoffs_total,
            categories=cat_out,
        )
