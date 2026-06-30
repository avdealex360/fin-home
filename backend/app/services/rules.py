from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session, joinedload

from app.models import Category, Debt, MonthlyPlan, SinkingFund, Transaction  # Goal removed in two-pots redesign (Task 1)
from app.services.allocation import get_unallocated_total
from app.services.settings_store import get_setting, set_setting
from app.services.dashboard import DashboardService
from app.services.debts import monthly_interest_cost
from app.services.sinking_funds import SinkingFundService


@dataclass
class Advice:
    priority: int
    message: str
    category: str = "info"
    tier: str = "info"  # urgent, attention, info


class Rule:
    priority: int = 50
    category: str = "info"
    tier: str = "info"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        raise NotImplementedError


class UnallocatedMoneyRule(Rule):
    priority = 95
    category = "danger"
    tier = "urgent"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        unallocated = get_unallocated_total(db, year, month)
        if unallocated <= Decimal("5000"):
            return None
        oldest = (
            db.query(Transaction)
            .filter(
                Transaction.type == "income",
                Transaction.is_fully_allocated.is_(False),
                extract("year", Transaction.date) == year,
                extract("month", Transaction.date) == month,
            )
            .order_by(Transaction.date.asc())
            .first()
        )
        if not oldest or (today - oldest.date).days < 3:
            return None
        return Advice(
            priority=self.priority,
            message=f"Нераспределено {unallocated:,.0f} ₽ — каждый рубль должен получить назначение".replace(",", " "),
            category=self.category,
            tier=self.tier,
        )


class CreditCardGraceRule(Rule):
    priority = 100
    category = "danger"
    tier = "urgent"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        debt = (
            db.query(Debt)
            .filter(Debt.type == "credit_card", Debt.is_closed.is_(False))
            .first()
        )
        if not debt or not debt.grace_period_end:
            return None
        days_left = (debt.grace_period_end - today).days
        if 0 <= days_left <= 7:
            return Advice(
                priority=self.priority,
                message=f"Погасите кредитку до {debt.grace_period_end.strftime('%d.%m.%Y')} чтобы избежать процентов",
                category=self.category,
                tier=self.tier,
            )
        return None


class SplitPaymentDueRule(Rule):
    priority = 98
    category = "danger"
    tier = "urgent"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        split = db.query(Debt).filter(Debt.type == "split", Debt.is_closed.is_(False)).first()
        if not split or not split.next_payment_date:
            return None
        days_left = (split.next_payment_date - today).days
        if 0 <= days_left <= 3:
            return Advice(
                priority=self.priority,
                message=f"Платёж Сплит {split.monthly_payment:,.0f} ₽ через {days_left} дн.".replace(",", " "),
                category=self.category,
                tier=self.tier,
            )
        return None


class CategoryOverBudgetRule(Rule):
    priority = 90
    category = "danger"
    tier = "urgent"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        plan = (
            db.query(MonthlyPlan)
            .options(joinedload(MonthlyPlan.limits))
            .filter(MonthlyPlan.year == year, MonthlyPlan.month == month)
            .first()
        )
        if not plan:
            return None
        for cat in db.query(Category).filter(Category.is_hidden.is_(False)).all():
            limit = next((lim.limit_amount for lim in plan.limits if lim.category_id == cat.id), None)
            if not limit or limit <= 0:
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
            if spent > limit:
                return Advice(
                    priority=self.priority,
                    message=f'«{cat.name}» в минусе: перерасход {(spent - limit):,.0f} ₽'.replace(",", " "),
                    category=self.category,
                    tier=self.tier,
                )
        return None


class CategoryLimitRule(Rule):
    priority = 80
    category = "warning"
    tier = "attention"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        summary = DashboardService.get_month_summary(db, year, month)
        if not summary.has_plan:
            return None
        plan = (
            db.query(MonthlyPlan)
            .options(joinedload(MonthlyPlan.limits))
            .filter(MonthlyPlan.year == year, MonthlyPlan.month == month)
            .first()
        )
        if not plan:
            return None
        categories = db.query(Category).filter(Category.is_hidden.is_(False)).all()
        worst: Advice | None = None
        worst_ratio = Decimal("0")
        for cat in categories:
            limit = next(
                (lim.limit_amount for lim in plan.limits if lim.category_id == cat.id),
                None,
            )
            if not limit or limit <= 0:
                group_pct = {"needs": 50, "wants": 30, "savings": 20}.get(cat.group, 0)
                limit = plan.expected_income * Decimal(group_pct) / Decimal("100")
                cat_count = db.query(Category).filter(Category.group == cat.group).count()
                if cat_count > 0:
                    limit = limit / cat_count
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
            if limit > 0 and spent / limit >= Decimal("0.85"):
                ratio = spent / limit
                remaining = limit - spent
                if ratio > worst_ratio:
                    worst_ratio = ratio
                    worst = Advice(
                        priority=self.priority,
                        message=f'В категории «{cat.name}» осталось {remaining:,.0f} ₽ до конца месяца'.replace(",", " "),
                        category="warning" if spent <= limit else "danger",
                        tier=self.tier,
                    )
        return worst


class SpendingPaceRule(Rule):
    priority = 78
    category = "warning"
    tier = "attention"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        if today.day < 15:
            return None
        plan = (
            db.query(MonthlyPlan)
            .options(joinedload(MonthlyPlan.limits))
            .filter(MonthlyPlan.year == year, MonthlyPlan.month == month)
            .first()
        )
        if not plan:
            return None
        days_in_month = 30
        day_fraction = Decimal(str(today.day)) / Decimal(str(days_in_month))
        for cat in db.query(Category).filter(Category.group == "wants", Category.is_hidden.is_(False)).all():
            limit = next((lim.limit_amount for lim in plan.limits if lim.category_id == cat.id), None)
            if not limit or limit <= 0:
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
            if spent / limit >= Decimal("0.7") and day_fraction < Decimal("0.6"):
                projected = (spent / day_fraction).quantize(Decimal("1"))
                pct = float(projected / limit * 100)
                remaining = limit - spent
                return Advice(
                    priority=self.priority,
                    message=(
                        f'«{cat.name}»: при текущем темпе выйдете на {pct:.0f}% лимита. '
                        f'Осталось {remaining:,.0f} ₽'.replace(",", " ")
                    ),
                    category=self.category,
                    tier=self.tier,
                )
        return None


class SinkingFundStaleRule(Rule):
    priority = 72
    category = "warning"
    tier = "attention"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        funds = db.query(SinkingFund).filter(SinkingFund.is_active.is_(True)).all()
        for fund in funds:
            last = SinkingFundService.last_contribution_date(db, fund.id)
            if last and (today - last).days < 60:
                continue
            if not last and fund.current_amount == 0:
                return Advice(
                    priority=self.priority,
                    message=(
                        f'«{fund.name}» не пополнялась 2+ месяца. '
                        f'Взнос {fund.monthly_contribution:,.0f} ₽ в этом месяце'.replace(",", " ")
                    ),
                    category=self.category,
                    tier=self.tier,
                )
        return None


class LowSavingsRule(Rule):
    priority = 70
    category = "warning"
    tier = "attention"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        if today.day < 20:
            return None
        summary = DashboardService.get_month_summary(db, year, month)
        if summary.income_fact <= 0:
            return None
        if summary.savings_rate < 15:
            return Advice(
                priority=self.priority,
                message=f"Сбережения {summary.savings_rate:.0f}% — цель 20% к 20-му числу",
                category=self.category,
                tier=self.tier,
            )
        return None


class CreditVsSplitRule(Rule):
    priority = 68
    category = "warning"
    tier = "attention"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        summary = DashboardService.get_month_summary(db, year, month)
        if summary.remaining <= Decimal("1000"):
            return None
        credit = db.query(Debt).filter(Debt.type == "credit_card", Debt.is_closed.is_(False)).first()
        if not credit or credit.interest_rate <= 0:
            return None
        cost = monthly_interest_cost(credit)
        return Advice(
            priority=self.priority,
            message=(
                f"Остаток {summary.remaining:,.0f} ₽. Кредитка под {credit.interest_rate}% — "
                f"каждый месяц ~{cost:,.0f} ₽. Направить на погашение?".replace(",", " ")
            ),
            category=self.category,
            tier=self.tier,
        )


class NextMonthPlanningRule(Rule):
    priority = 45
    category = "info"
    tier = "info"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        if today.day < 25:
            return None
        days_left = 30 - today.day
        return Advice(
            priority=self.priority,
            message=f"До конца месяца {days_left} дн. Наметить план на следующий месяц?",
            category=self.category,
            tier=self.tier,
        )


class EurIncomeRule(Rule):
    priority = 40
    category = "info"
    tier = "info"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        from app.services.exchange import get_eur_rub_rate

        salary_tx = (
            db.query(Transaction)
            .join(Category)
            .filter(
                Transaction.type == "income",
                Category.name == "Зарплата",
                extract("year", Transaction.date) == year,
                extract("month", Transaction.date) == month,
            )
            .order_by(Transaction.date.desc())
            .first()
        )
        if not salary_tx or not salary_tx.base_amount_eur:
            return None
        rate = salary_tx.exchange_rate or get_eur_rub_rate(db)
        diff_msg = ""
        if summary := DashboardService.get_month_summary(db, year, month):
            if summary.salary_diff is not None:
                sign = "+" if summary.salary_diff >= 0 else ""
                diff_msg = f" ({sign}{summary.salary_diff:,.0f} ₽ vs прошлый месяц)".replace(",", " ")
        return Advice(
            priority=self.priority,
            message=(
                f"Зарплата €{salary_tx.base_amount_eur} × {rate} = {salary_tx.amount:,.0f} ₽{diff_msg}".replace(",", " ")
            ),
            category=self.category,
            tier=self.tier,
        )


class LargeExpenseRule(Rule):
    priority = 75
    category = "warning"
    tier = "attention"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        summary = DashboardService.get_month_summary(db, year, month)
        if summary.income_fact <= 0:
            return None
        threshold = summary.income_fact * Decimal("0.2")
        big = (
            db.query(Transaction)
            .filter(
                Transaction.type == "expense",
                Transaction.amount >= threshold,
                extract("year", Transaction.date) == year,
                extract("month", Transaction.date) == month,
            )
            .order_by(Transaction.amount.desc())
            .first()
        )
        if big:
            return Advice(
                priority=self.priority,
                message=f"Большая трата {big.amount:,.0f} ₽ — проверьте план на месяц".replace(",", " "),
                category=self.category,
                tier=self.tier,
            )
        return None


class PartnerIncomeRule(Rule):
    priority = 60
    category = "info"
    tier = "info"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        if today.day <= 10:
            return None
        income_count = (
            db.query(func.count(Transaction.id))
            .filter(
                Transaction.type == "income",
                extract("year", Transaction.date) == year,
                extract("month", Transaction.date) == month,
            )
            .scalar()
        )
        if not income_count:
            return Advice(
                priority=self.priority,
                message="Не забудьте внести доход за текущий месяц",
                category=self.category,
                tier=self.tier,
            )
        return None


class DepositStaleRule(Rule):
    priority = 65
    category = "warning"
    tier = "attention"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        from app.models import DepositSnapshot

        last = db.query(func.max(DepositSnapshot.date)).scalar()
        if last and (today - last).days > 30:
            return Advice(
                priority=self.priority,
                message="Вклад не пополнялся больше месяца — не забудьте пополнить",
                category=self.category,
                tier=self.tier,
            )
        return None


class DebtClosedRule(Rule):
    priority = 50
    category = "success"
    tier = "info"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        closed = (
            db.query(Debt)
            .filter(Debt.is_closed.is_(True), Debt.remaining <= 0)
            .order_by(Debt.id.desc())
            .first()
        )
        if closed and closed.monthly_payment > 0:
            key = f"debt_closed_notified_{closed.id}"
            if get_setting(db, key) != "1":
                credit = db.query(Debt).filter(Debt.type == "credit_card", Debt.is_closed.is_(False)).first()
                if credit:
                    months = int((credit.remaining / closed.monthly_payment).to_integral_value())
                    return Advice(
                        priority=self.priority,
                        message=(
                            f"{closed.name} закрыт! Направить {closed.monthly_payment:,.0f} ₽/мес на кредитку — "
                            f"закроется через ~{months} мес.".replace(",", " ")
                        ),
                        category=self.category,
                        tier=self.tier,
                    )
                return Advice(
                    priority=self.priority,
                    message=f"{closed.name} закрыт! {closed.monthly_payment:,.0f} ₽/мес можно направить в подушку".replace(",", " "),
                    category=self.category,
                    tier=self.tier,
                )
        return None


class EmergencyFundRule(Rule):
    priority = 55
    category = "success"
    tier = "info"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        # Goals removed in two-pots redesign; this rule no longer fires
        return None


class HealthExpenseRule(Rule):
    priority = 65
    category = "warning"
    tier = "attention"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        health_cat = db.query(Category).filter(Category.name == "Здоровье и лекарства").first()
        if not health_cat:
            return None
        spent = (
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.type == "expense",
                Transaction.category_id == health_cat.id,
                extract("year", Transaction.date) == year,
                extract("month", Transaction.date) == month,
            )
            .scalar()
        ) or Decimal("0")
        if spent > Decimal("20000"):
            return Advice(
                priority=self.priority,
                message="Расходы на врачей выросли — может стоить посмотреть ДМС?",
                category=self.category,
                tier=self.tier,
            )
        return None


class QuarterlyCheckupRule(Rule):
    priority = 42
    category = "info"
    tier = "info"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        if today.day > 7 or today.month not in (1, 4, 7, 10):
            return None
        if get_setting(db, f"checkup_{today.year}_Q{(today.month - 1) // 3 + 1}") == "1":
            return None
        return Advice(
            priority=self.priority,
            message="Ежеквартальный чекап: пересмотрите копилки, 50/30/20 и цели",
            category=self.category,
            tier=self.tier,
        )


ALL_RULES: list[Rule] = [
    CreditCardGraceRule(),
    SplitPaymentDueRule(),
    UnallocatedMoneyRule(),
    CategoryOverBudgetRule(),
    CategoryLimitRule(),
    SpendingPaceRule(),
    LargeExpenseRule(),
    SinkingFundStaleRule(),
    LowSavingsRule(),
    CreditVsSplitRule(),
    HealthExpenseRule(),
    DepositStaleRule(),
    PartnerIncomeRule(),
    EmergencyFundRule(),
    DebtClosedRule(),
    EurIncomeRule(),
    NextMonthPlanningRule(),
    QuarterlyCheckupRule(),
]

TIER_LIMITS = {"urgent": 2, "attention": 2, "info": 1}


class RuleEngine:
    @staticmethod
    def evaluate(db: Session, year: int, month: int) -> dict[str, list[Advice]]:
        today = date.today()
        results: list[Advice] = []
        for rule in ALL_RULES:
            advice = rule.evaluate(db, year, month, today)
            if advice:
                results.append(advice)
        results.sort(key=lambda a: a.priority, reverse=True)

        tiers: dict[str, list[Advice]] = {"urgent": [], "attention": [], "info": []}
        for advice in results:
            tier = advice.tier
            if len(tiers[tier]) < TIER_LIMITS[tier]:
                tiers[tier].append(advice)
        return tiers

    @staticmethod
    def evaluate_flat(db: Session, year: int, month: int, max_advice: int = 5) -> list[Advice]:
        tiers = RuleEngine.evaluate(db, year, month)
        flat: list[Advice] = []
        for tier in ("urgent", "attention", "info"):
            flat.extend(tiers[tier])
        return flat[:max_advice]

    @staticmethod
    def mark_shown(db: Session, advice_tiers: dict[str, list[Advice]]) -> None:
        from app.models import Debt

        for tier_list in advice_tiers.values():
            for advice in tier_list:
                if "закрыт!" in advice.message.lower() or "закрыт." in advice.message.lower():
                    closed = db.query(Debt).filter(Debt.is_closed.is_(True)).order_by(Debt.id.desc()).first()
                    if closed:
                        set_setting(db, f"debt_closed_notified_{closed.id}", "1")
                if "Ежеквартальный чекап" in advice.message:
                    today = date.today()
                    set_setting(db, f"checkup_{today.year}_Q{(today.month - 1) // 3 + 1}", "1")
