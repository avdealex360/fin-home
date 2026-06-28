from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session, joinedload

from app.models import Category, Debt, Goal, MonthlyPlan, Setting, Transaction
from app.seed import GROUP_PERCENTS


@dataclass
class GroupSummary:
    name: str
    label: str
    percent: int
    limit: Decimal
    spent: Decimal
    remaining: Decimal
    usage_percent: float
    color: str


@dataclass
class DebtSummary:
    id: int
    name: str
    remaining: Decimal
    total_amount: Decimal
    progress_percent: float
    monthly_payment: Decimal
    grace_period_end: date | None
    next_payment_date: date | None
    type: str
    is_closed: bool


@dataclass
class GoalSummary:
    id: int
    name: str
    current_amount: Decimal
    target_amount: Decimal
    progress_percent: float
    months_to_goal: int | None
    deadline: date | None


@dataclass
class MonthSummary:
    year: int
    month: int
    income_fact: Decimal
    income_plan: Decimal
    total_spent: Decimal
    remaining: Decimal
    savings_rate: float
    savings_target_rate: float = 20.0
    deposit_balance: Decimal = Decimal("0")
    groups: list[GroupSummary] = field(default_factory=list)
    debts: list[DebtSummary] = field(default_factory=list)
    goals: list[GoalSummary] = field(default_factory=list)
    has_plan: bool = False


GROUP_LABELS = {"needs": "Нужды (50%)", "wants": "Желания (30%)", "savings": "Сбережения (20%)"}


def _usage_color(percent: float) -> str:
    if percent < 80:
        return "green"
    if percent <= 100:
        return "yellow"
    return "red"


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()


class DashboardService:
    @staticmethod
    def get_month_summary(db: Session, year: int, month: int) -> MonthSummary:
        plan = (
            db.query(MonthlyPlan)
            .options(joinedload(MonthlyPlan.limits))
            .filter(MonthlyPlan.year == year, MonthlyPlan.month == month)
            .first()
        )
        income_plan = plan.expected_income if plan else Decimal("0")

        income_fact = (
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.type == "income",
                extract("year", Transaction.date) == year,
                extract("month", Transaction.date) == month,
            )
            .scalar()
        ) or Decimal("0")

        total_spent = (
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.type == "expense",
                extract("year", Transaction.date) == year,
                extract("month", Transaction.date) == month,
            )
            .scalar()
        ) or Decimal("0")

        savings_spent = (
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .join(Category)
            .filter(
                Transaction.type.in_(["expense", "transfer"]),
                Category.group == "savings",
                extract("year", Transaction.date) == year,
                extract("month", Transaction.date) == month,
            )
            .scalar()
        ) or Decimal("0")

        savings_rate = float(savings_spent / income_fact * 100) if income_fact > 0 else 0.0
        remaining = income_fact - total_spent
        deposit_balance = Decimal(get_setting(db, "deposit_balance", "0"))

        groups = []
        for group_name, percent in GROUP_PERCENTS.items():
            group_limit = DashboardService._group_limit(db, plan, group_name, income_plan, percent)
            spent = DashboardService._group_spent(db, year, month, group_name)
            rem = group_limit - spent
            usage = float(spent / group_limit * 100) if group_limit > 0 else 0.0
            groups.append(
                GroupSummary(
                    name=group_name,
                    label=GROUP_LABELS[group_name],
                    percent=percent,
                    limit=group_limit,
                    spent=spent,
                    remaining=rem,
                    usage_percent=usage,
                    color=_usage_color(usage),
                )
            )

        debts = []
        for debt in db.query(Debt).order_by(Debt.id).all():
            progress = (
                float((debt.total_amount - debt.remaining) / debt.total_amount * 100)
                if debt.total_amount > 0
                else 0.0
            )
            debts.append(
                DebtSummary(
                    id=debt.id,
                    name=debt.name,
                    remaining=debt.remaining,
                    total_amount=debt.total_amount,
                    progress_percent=progress,
                    monthly_payment=debt.monthly_payment,
                    grace_period_end=debt.grace_period_end,
                    next_payment_date=debt.next_payment_date,
                    type=debt.type,
                    is_closed=debt.is_closed,
                )
            )

        goals = []
        for goal in db.query(Goal).filter(Goal.is_active).order_by(Goal.id).all():
            progress = (
                float(goal.current_amount / goal.target_amount * 100)
                if goal.target_amount > 0
                else 0.0
            )
            months = None
            if goal.monthly_contribution > 0 and goal.target_amount > goal.current_amount:
                remaining_goal = goal.target_amount - goal.current_amount
                months = int((remaining_goal / goal.monthly_contribution).to_integral_value())
            goals.append(
                GoalSummary(
                    id=goal.id,
                    name=goal.name,
                    current_amount=goal.current_amount,
                    target_amount=goal.target_amount,
                    progress_percent=progress,
                    months_to_goal=months,
                    deadline=goal.deadline,
                )
            )

        return MonthSummary(
            year=year,
            month=month,
            income_fact=income_fact,
            income_plan=income_plan,
            total_spent=total_spent,
            remaining=remaining,
            savings_rate=savings_rate,
            deposit_balance=deposit_balance,
            groups=groups,
            debts=debts,
            goals=goals,
            has_plan=plan is not None and income_plan > 0,
        )

    @staticmethod
    def _group_limit(
        db: Session,
        plan: MonthlyPlan | None,
        group: str,
        income_plan: Decimal,
        percent: int,
    ) -> Decimal:
        if plan and plan.limits:
            cat_ids = [c.id for c in db.query(Category).filter(Category.group == group).all()]
            total = sum(
                (lim.limit_amount for lim in plan.limits if lim.category_id in cat_ids),
                Decimal("0"),
            )
            if total > 0:
                return total
        return income_plan * Decimal(percent) / Decimal("100")

    @staticmethod
    def _group_spent(db: Session, year: int, month: int, group: str) -> Decimal:
        result = (
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .join(Category)
            .filter(
                Transaction.type == "expense",
                Category.group == group,
                extract("year", Transaction.date) == year,
                extract("month", Transaction.date) == month,
            )
            .scalar()
        )
        return result or Decimal("0")
