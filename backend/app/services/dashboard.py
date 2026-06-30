from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session, joinedload

from app.models import Category, MonthlyPlan, Transaction
from app.seed import GROUP_PERCENTS
from app.services.allocation import get_unallocated_total, is_month_fully_allocated
from app.services.debts import get_active_debts_sorted, monthly_interest_cost
from app.services.deposit import DepositService
from app.services.exchange import income_eur_total, salary_comparison
from app.services.sinking_funds import FundSummary, SinkingFundService


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
    interest_rate: Decimal = Decimal("0")
    priority_rank: int | None = None
    monthly_interest: Decimal = Decimal("0")
    priority_label: str = ""


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
    income_eur: Decimal = Decimal("0")
    unallocated: Decimal = Decimal("0")
    is_fully_allocated: bool = True
    income_eur_rate: Decimal | None = None
    salary_last_month: Decimal | None = None
    salary_diff: Decimal | None = None
    groups: list[GroupSummary] = field(default_factory=list)
    debts: list[DebtSummary] = field(default_factory=list)
    funds: list[FundSummary] = field(default_factory=list)
    has_plan: bool = False


GROUP_LABELS = {"needs": "Нужды (50%)", "wants": "Желания (30%)", "savings": "Сбережения (20%)"}


def _usage_color(percent: float) -> str:
    if percent < 70:
        return "green"
    if percent < 90:
        return "yellow"
    return "red"


def _savings_set_aside(db: Session, year: int, month: int) -> Decimal:
    from app.models import DepositContribution, SinkingFund, SinkingFundContribution
    dep = (
        db.query(func.coalesce(func.sum(DepositContribution.amount), 0))
        .filter(extract("year", DepositContribution.date) == year,
                extract("month", DepositContribution.date) == month)
        .scalar()
    ) or Decimal("0")
    fund = (
        db.query(func.coalesce(func.sum(SinkingFundContribution.amount), 0))
        .join(SinkingFund, SinkingFund.id == SinkingFundContribution.fund_id)
        .filter(SinkingFund.group == "savings",
                extract("year", SinkingFundContribution.date) == year,
                extract("month", SinkingFundContribution.date) == month)
        .scalar()
    ) or Decimal("0")
    return Decimal(dep) + Decimal(fund)


from app.services.settings_store import get_setting, set_setting


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

        savings_spent = _savings_set_aside(db, year, month)
        savings_rate = float(savings_spent / income_fact * 100) if income_fact > 0 else 0.0
        remaining = income_fact - total_spent
        deposit_balance = Decimal(get_setting(db, "deposit_balance", "0"))
        income_eur = income_eur_total(db, year, month)
        unallocated = get_unallocated_total(db, year, month)
        fully_allocated = is_month_fully_allocated(db, year, month)

        last_salary, salary_diff = salary_comparison(db, year, month, income_fact)

        income_base = income_plan or income_fact

        groups = []
        for group_name, percent in GROUP_PERCENTS.items():
            if group_name == "savings":
                spent = _savings_set_aside(db, year, month)
                group_limit = income_base * Decimal(percent) / Decimal("100")
            else:
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

        debts_raw = get_active_debts_sorted(db)
        debts = []
        for debt_row in debts_raw:
            progress = (
                float((debt_row.total_amount - debt_row.remaining) / debt_row.total_amount * 100)
                if debt_row.total_amount > 0
                else 0.0
            )
            interest = monthly_interest_cost(debt_row)
            label = ""
            if debt_row.interest_rate >= Decimal("10"):
                label = "Приоритет"
            elif debt_row.interest_rate <= 0:
                label = "Не срочно"
            debts.append(
                DebtSummary(
                    id=debt_row.id,
                    name=debt_row.name,
                    remaining=debt_row.remaining,
                    total_amount=debt_row.total_amount,
                    progress_percent=progress,
                    monthly_payment=debt_row.monthly_payment,
                    grace_period_end=debt_row.grace_period_end,
                    next_payment_date=debt_row.next_payment_date,
                    type=debt_row.type,
                    is_closed=debt_row.is_closed,
                    interest_rate=debt_row.interest_rate,
                    priority_rank=debt_row.priority_rank,
                    monthly_interest=interest,
                    priority_label=label,
                )
            )

        funds = SinkingFundService.get_summaries(db)

        return MonthSummary(
            year=year,
            month=month,
            income_fact=income_fact,
            income_plan=income_plan,
            total_spent=total_spent,
            remaining=remaining,
            savings_rate=savings_rate,
            deposit_balance=deposit_balance,
            income_eur=income_eur,
            unallocated=unallocated,
            is_fully_allocated=fully_allocated,
            salary_last_month=last_salary,
            salary_diff=salary_diff,
            groups=groups,
            debts=debts,
            funds=funds,
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
                (lim.limit_amount + (lim.carried_over or Decimal("0")) for lim in plan.limits if lim.category_id in cat_ids),
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
