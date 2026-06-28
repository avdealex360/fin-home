from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session, joinedload

from app.models import Category, Debt, Goal, MonthlyPlan, Transaction
from app.services.dashboard import DashboardService, get_setting


@dataclass
class Advice:
    priority: int
    message: str
    category: str = "info"


class Rule:
    priority: int = 50
    category: str = "info"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        raise NotImplementedError


class CategoryLimitRule(Rule):
    priority = 80
    category = "warning"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        summary = DashboardService.get_month_summary(db, year, month)
        if not summary.has_plan:
            return None

        plan = (
            db.query(MonthlyPlan)
            .options(joinedload(MonthlyPlan.limits).joinedload("category"))
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

            if limit > 0 and spent / limit > Decimal("0.8"):
                ratio = spent / limit
                remaining = limit - spent
                if ratio > worst_ratio:
                    worst_ratio = ratio
                    worst = Advice(
                        priority=self.priority,
                        message=f'В категории «{cat.name}» осталось {remaining:,.0f} ₽ до конца месяца'.replace(",", " "),
                        category="warning" if spent <= limit else "danger",
                    )

        return worst


class CreditCardGraceRule(Rule):
    priority = 100
    category = "danger"

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
                category="danger",
            )
        return None


class LowSavingsRule(Rule):
    priority = 70
    category = "warning"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        if today.day < 15:
            return None
        summary = DashboardService.get_month_summary(db, year, month)
        if summary.income_fact <= 0:
            return None
        if summary.savings_rate < 10:
            target = summary.income_fact * Decimal("0.2") - (
                summary.income_fact * Decimal(str(summary.savings_rate)) / Decimal("100")
            )
            return Advice(
                priority=self.priority,
                message=f"Вы откладываете меньше 10% — попробуйте перенести {target:,.0f} ₽ из «желаний» в накопления".replace(",", " "),
                category="warning",
            )
        return None


class PartnerIncomeRule(Rule):
    priority = 60
    category = "info"

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
                category="info",
            )
        return None


class DepositStaleRule(Rule):
    priority = 65
    category = "warning"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        from app.models import DepositSnapshot

        last = db.query(func.max(DepositSnapshot.date)).scalar()
        if last and (today - last).days > 30:
            goal = db.query(Goal).filter(Goal.name == "Машина").first()
            contrib = goal.monthly_contribution if goal else Decimal("5000")
            return Advice(
                priority=self.priority,
                message=f"Вклад на машину не пополнялся месяц — добавьте хотя бы {contrib:,.0f} ₽".replace(",", " "),
                category="warning",
            )
        return None


class LargeExpenseRule(Rule):
    priority = 75
    category = "warning"

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
                message=f"Большая трата {big.amount:,.0f} ₽ — проверьте, не нужно ли скорректировать план на месяц".replace(",", " "),
                category="warning",
            )
        return None


class DebtClosedRule(Rule):
    priority = 50
    category = "success"

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
                return Advice(
                    priority=self.priority,
                    message=f"Кредитка закрыта! Теперь {closed.monthly_payment:,.0f} ₽ можно направить в подушку безопасности".replace(",", " "),
                    category="success",
                )
        return None


class EmergencyFundRule(Rule):
    priority = 55
    category = "success"

    def evaluate(self, db: Session, year: int, month: int, today: date) -> Advice | None:
        goal = db.query(Goal).filter(Goal.name == "Подушка безопасности").first()
        if not goal:
            return None
        if goal.current_amount >= Decimal("150000") and get_setting(db, "pillow_150k_notified") != "1":
            return Advice(
                priority=self.priority,
                message="Подушка безопасности 150 000 ₽ собрана! Следующая цель — 500 000 ₽",
                category="success",
            )
        return None


class HealthExpenseRule(Rule):
    priority = 65
    category = "warning"

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
                category="warning",
            )
        return None


ALL_RULES: list[Rule] = [
    CreditCardGraceRule(),
    CategoryLimitRule(),
    LargeExpenseRule(),
    LowSavingsRule(),
    HealthExpenseRule(),
    DepositStaleRule(),
    PartnerIncomeRule(),
    EmergencyFundRule(),
    DebtClosedRule(),
]


class RuleEngine:
    @staticmethod
    def evaluate(db: Session, year: int, month: int, max_advice: int = 3) -> list[Advice]:
        today = date.today()
        results: list[Advice] = []
        for rule in ALL_RULES:
            advice = rule.evaluate(db, year, month, today)
            if advice:
                results.append(advice)
        results.sort(key=lambda a: a.priority, reverse=True)
        return results[:max_advice]
