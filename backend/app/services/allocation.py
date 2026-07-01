from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session, joinedload

from app.models import Category, CategoryLimit, IncomeAllocation, MonthlyPlan, SinkingFund, Transaction
from app.seed import GROUP_PERCENTS

BUCKETS = [("needs", "Нужды", 50), ("wants", "Желания", 30), ("savings", "Сбережения", 20)]


@dataclass
class AllocationItem:
    id: int
    name: str
    kind: str  # category | fund | deposit
    suggested_amount: Decimal
    group: str


@dataclass
class AllocationBucket:
    group: str
    label: str
    percent: int
    target_amount: Decimal
    items: list[AllocationItem] = field(default_factory=list)


def get_allocated_amount(db: Session, income_tx_id: int) -> Decimal:
    result = (
        db.query(func.coalesce(func.sum(IncomeAllocation.amount), 0))
        .filter(IncomeAllocation.income_tx_id == income_tx_id)
        .scalar()
    )
    return result or Decimal("0")


def get_unallocated_for_tx(db: Session, income_tx: Transaction) -> Decimal:
    allocated = get_allocated_amount(db, income_tx.id)
    return income_tx.amount - allocated


def get_unallocated_total(db: Session, year: int, month: int) -> Decimal:
    incomes = (
        db.query(Transaction)
        .filter(
            Transaction.type == "income",
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) == month,
        )
        .all()
    )
    total = Decimal("0")
    for tx in incomes:
        if not tx.is_fully_allocated:
            total += get_unallocated_for_tx(db, tx)
    return total


def is_month_fully_allocated(db: Session, year: int, month: int) -> bool:
    incomes = (
        db.query(Transaction)
        .filter(
            Transaction.type == "income",
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) == month,
        )
        .all()
    )
    if not incomes:
        return True
    return all(tx.is_fully_allocated for tx in incomes)


def _limit_for_category(db: Session, plan: MonthlyPlan | None, cat: Category) -> Decimal:
    if plan and plan.limits:
        for lim in plan.limits:
            if lim.category_id == cat.id:
                carried = lim.carried_over or Decimal("0")
                return lim.limit_amount + carried
    if plan and plan.expected_income > 0:
        group_pct = GROUP_PERCENTS.get(cat.group, 0)
        group_total = plan.expected_income * Decimal(group_pct) / Decimal("100")
        cats_in_group = (
            db.query(Category)
            .filter(Category.group == cat.group, Category.is_hidden.is_(False))
            .count()
        )
        if cats_in_group > 0:
            return group_total / cats_in_group
    return Decimal("0")


def get_allocation_buckets(
    db: Session, year: int, month: int, income_amount: Decimal
) -> list[AllocationBucket]:
    plan = (
        db.query(MonthlyPlan)
        .options(joinedload(MonthlyPlan.limits))
        .filter(MonthlyPlan.year == year, MonthlyPlan.month == month)
        .first()
    )
    out: list[AllocationBucket] = []
    for group, label, percent in BUCKETS:
        target = (income_amount * Decimal(percent) / Decimal("100")).quantize(Decimal("0.01"))
        bucket = AllocationBucket(group=group, label=label, percent=percent, target_amount=target)

        if group in ("needs", "wants", "savings"):
            cats = (
                db.query(Category)
                .filter(Category.is_hidden.is_(False), Category.group == group)
                .order_by(Category.sort_order)
                .all()
            )
            for cat in cats:
                bucket.items.append(
                    AllocationItem(
                        id=cat.id,
                        name=cat.name,
                        kind="category",
                        suggested_amount=_limit_for_category(db, plan, cat),
                        group=group,
                    )
                )

        funds = (
            db.query(SinkingFund)
            .filter(SinkingFund.is_active.is_(True), SinkingFund.group == group)
            .order_by(SinkingFund.id)
            .all()
        )
        for f in funds:
            bucket.items.append(
                AllocationItem(
                    id=f.id,
                    name=f.name,
                    kind="fund",
                    suggested_amount=f.monthly_contribution,
                    group=group,
                )
            )

        out.append(bucket)
    return out


@dataclass
class AllocationInput:
    category_id: int | None = None
    fund_id: int | None = None
    amount: Decimal = Decimal("0")
    group: str = "needs"


def allocate_income(
    db: Session,
    income_tx_id: int,
    allocations: list[AllocationInput],
) -> Transaction:
    tx = db.query(Transaction).filter(Transaction.id == income_tx_id).first()
    if not tx or tx.type != "income":
        raise ValueError("Invalid income transaction")

    old = db.query(IncomeAllocation).filter(IncomeAllocation.income_tx_id == income_tx_id).all()
    for o in old:
        if o.fund_id:
            f = db.query(SinkingFund).filter(SinkingFund.id == o.fund_id).first()
            if f:
                f.current_amount = max(Decimal("0"), f.current_amount - o.amount)
    db.query(IncomeAllocation).filter(IncomeAllocation.income_tx_id == income_tx_id).delete()

    total = Decimal("0")
    for a in allocations:
        if a.amount <= 0:
            continue
        db.add(
            IncomeAllocation(
                income_tx_id=income_tx_id,
                category_id=a.category_id,
                fund_id=a.fund_id,
                amount=a.amount,
                allocated_at=datetime.utcnow(),
                allocation_level=0,
            )
        )
        total += a.amount
        if a.fund_id:
            f = db.query(SinkingFund).filter(SinkingFund.id == a.fund_id).first()
            if f:
                f.current_amount += a.amount

    tx.is_fully_allocated = abs(total - tx.amount) <= Decimal("0.01")
    db.commit()
    db.refresh(tx)
    return tx


def close_month(db: Session, year: int, month: int) -> MonthlyPlan:
    from datetime import date as date_type

    from app.util import _shift_month

    plan = (
        db.query(MonthlyPlan)
        .options(joinedload(MonthlyPlan.limits))
        .filter(MonthlyPlan.year == year, MonthlyPlan.month == month)
        .first()
    )
    if not plan:
        raise ValueError("Plan not found")

    plan.is_closed = True
    plan.closed_at = datetime.utcnow()

    next_year, next_month = _shift_month(year, month, 1)
    next_plan = (
        db.query(MonthlyPlan)
        .filter(MonthlyPlan.year == next_year, MonthlyPlan.month == next_month)
        .first()
    )
    if not next_plan:
        from app.services.plan import PlanService

        next_plan = PlanService.get_or_create_plan(db, next_year, next_month)

    categories = db.query(Category).filter(Category.is_hidden.is_(False)).all()
    for cat in categories:
        limit = next(
            (lim for lim in plan.limits if lim.category_id == cat.id),
            None,
        )
        if not limit:
            continue
        spent = (
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.type == "expense",
                Transaction.category_id == cat.id,
                extract("year", Transaction.date) == year,
                extract("month", Transaction.date) == month,
            )
            .scalar()
        ) or Decimal("0")
        remaining = limit.limit_amount + (limit.carried_over or Decimal("0")) - spent
        if remaining > 0:
            existing = (
                db.query(CategoryLimit)
                .filter(
                    CategoryLimit.plan_id == next_plan.id,
                    CategoryLimit.category_id == cat.id,
                )
                .first()
            )
            if existing:
                existing.carried_over = (existing.carried_over or Decimal("0")) + remaining
            else:
                db.add(
                    CategoryLimit(
                        plan_id=next_plan.id,
                        category_id=cat.id,
                        limit_amount=Decimal("0"),
                        carried_over=remaining,
                    )
                )

    db.commit()
    db.refresh(plan)
    return plan
