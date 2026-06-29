from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session, joinedload

from app.models import Category, CategoryLimit, IncomeAllocation, MonthlyPlan, SinkingFund, Transaction
from app.seed import GROUP_PERCENTS


@dataclass
class AllocationItem:
    id: int
    name: str
    kind: str  # category | fund
    suggested_amount: Decimal
    group: str | None = None
    allocation_level: int = 0


@dataclass
class AllocationLevel:
    level: int
    label: str
    items: list[AllocationItem] = field(default_factory=list)
    total_suggested: Decimal = Decimal("0")


LEVEL_LABELS = {
    1: "Обязательства (фиксированные)",
    2: "Переменные нужды",
    3: "Взносы в копилки",
    4: "Желания и сбережения",
}


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


def get_allocation_levels(
    db: Session, year: int, month: int, income_amount: Decimal
) -> list[AllocationLevel]:
    plan = (
        db.query(MonthlyPlan)
        .options(joinedload(MonthlyPlan.limits))
        .filter(MonthlyPlan.year == year, MonthlyPlan.month == month)
        .first()
    )

    levels: dict[int, AllocationLevel] = {}
    for lvl, label in LEVEL_LABELS.items():
        levels[lvl] = AllocationLevel(level=lvl, label=label)

    categories = (
        db.query(Category)
        .filter(
            Category.is_hidden.is_(False),
            Category.group.in_(["needs", "wants", "savings"]),
            Category.allocation_level.in_([1, 2, 4]),
        )
        .order_by(Category.sort_order)
        .all()
    )

    l1_total = Decimal("0")
    l2_total = Decimal("0")

    for cat in categories:
        level = cat.allocation_level or 4
        if level == 3:
            continue
        amount = _limit_for_category(db, plan, cat)
        if level == 1:
            l1_total += amount
        elif level == 2:
            l2_total += amount
        levels[level].items.append(
            AllocationItem(
                id=cat.id,
                name=cat.name,
                kind="category",
                suggested_amount=amount,
                group=cat.group,
                allocation_level=level,
            )
        )
        levels[level].total_suggested += amount

    funds = (
        db.query(SinkingFund)
        .filter(SinkingFund.is_active.is_(True))
        .order_by(SinkingFund.id)
        .all()
    )
    for fund in funds:
        levels[3].items.append(
            AllocationItem(
                id=fund.id,
                name=fund.name,
                kind="fund",
                suggested_amount=fund.monthly_contribution,
                group=fund.category_group,
                allocation_level=3,
            )
        )
        levels[3].total_suggested += fund.monthly_contribution

    # L4: apply 50/30/20 to remainder after L1-L3
    remainder = income_amount - l1_total - l2_total - levels[3].total_suggested
    if remainder > 0 and levels[4].items:
        wants_cats = [i for i in levels[4].items if i.group == "wants"]
        savings_cats = [i for i in levels[4].items if i.group == "savings"]
        wants_total = remainder * Decimal("60") / Decimal("100")  # 30/50 of remainder ~ wants share
        savings_total = remainder - wants_total
        if wants_cats:
            per_want = wants_total / len(wants_cats)
            for item in wants_cats:
                item.suggested_amount = per_want.quantize(Decimal("0.01"))
        if savings_cats:
            per_save = savings_total / len(savings_cats)
            for item in savings_cats:
                item.suggested_amount = per_save.quantize(Decimal("0.01"))
        levels[4].total_suggested = sum(i.suggested_amount for i in levels[4].items)

    return [levels[i] for i in sorted(levels.keys())]


@dataclass
class AllocationInput:
    category_id: int | None = None
    fund_id: int | None = None
    amount: Decimal = Decimal("0")
    allocation_level: int = 1


def allocate_income(
    db: Session,
    income_tx_id: int,
    allocations: list[AllocationInput],
) -> Transaction:
    tx = db.query(Transaction).filter(Transaction.id == income_tx_id).first()
    if not tx or tx.type != "income":
        raise ValueError("Invalid income transaction")

    old_allocs = db.query(IncomeAllocation).filter(IncomeAllocation.income_tx_id == income_tx_id).all()
    for old in old_allocs:
        if old.fund_id:
            fund = db.query(SinkingFund).filter(SinkingFund.id == old.fund_id).first()
            if fund:
                fund.current_amount -= old.amount
                if fund.current_amount < 0:
                    fund.current_amount = Decimal("0")

    db.query(IncomeAllocation).filter(IncomeAllocation.income_tx_id == income_tx_id).delete()

    total = Decimal("0")
    for alloc in allocations:
        if alloc.amount <= 0:
            continue
        db.add(
            IncomeAllocation(
                income_tx_id=income_tx_id,
                category_id=alloc.category_id,
                fund_id=alloc.fund_id,
                amount=alloc.amount,
                allocated_at=datetime.utcnow(),
                allocation_level=alloc.allocation_level,
            )
        )
        total += alloc.amount
        if alloc.fund_id:
            fund = db.query(SinkingFund).filter(SinkingFund.id == alloc.fund_id).first()
            if fund:
                fund.current_amount += alloc.amount

    tx.is_fully_allocated = total == tx.amount or abs(total - tx.amount) <= Decimal("0.01")
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
