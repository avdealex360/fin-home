from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Category, CategoryLimit, MonthlyPlan
from app.seed import GROUP_PERCENTS
from app.services.dashboard import get_setting, set_setting


class PlanService:
    @staticmethod
    def get_or_create_plan(db: Session, year: int, month: int) -> MonthlyPlan:
        plan = db.query(MonthlyPlan).filter(MonthlyPlan.year == year, MonthlyPlan.month == month).first()
        if not plan:
            plan = MonthlyPlan(year=year, month=month, expected_income=Decimal("0"))
            db.add(plan)
            db.commit()
            db.refresh(plan)
        return plan

    @staticmethod
    def save_plan(
        db: Session,
        year: int,
        month: int,
        expected_income: Decimal,
        category_limits: dict[int, Decimal] | None = None,
        auto_distribute: bool = True,
    ) -> MonthlyPlan:
        plan = PlanService.get_or_create_plan(db, year, month)
        plan.expected_income = expected_income

        if auto_distribute and expected_income > 0:
            categories = db.query(Category).filter(Category.is_hidden.is_(False)).order_by(Category.sort_order).all()
            by_group: dict[str, list[Category]] = {}
            for cat in categories:
                by_group.setdefault(cat.group, []).append(cat)

            db.query(CategoryLimit).filter(CategoryLimit.plan_id == plan.id).delete()
            for group, cats in by_group.items():
                group_total = expected_income * Decimal(GROUP_PERCENTS[group]) / Decimal("100")
                per_cat = group_total / len(cats) if cats else Decimal("0")
                for cat in cats:
                    db.add(CategoryLimit(plan_id=plan.id, category_id=cat.id, limit_amount=per_cat))

        if category_limits:
            for cat_id, amount in category_limits.items():
                existing = (
                    db.query(CategoryLimit)
                    .filter(CategoryLimit.plan_id == plan.id, CategoryLimit.category_id == cat_id)
                    .first()
                )
                if existing:
                    existing.limit_amount = amount
                else:
                    db.add(CategoryLimit(plan_id=plan.id, category_id=cat_id, limit_amount=amount))

        db.commit()
        db.refresh(plan)
        return plan

    @staticmethod
    def get_plan_with_limits(db: Session, year: int, month: int) -> tuple[MonthlyPlan | None, list[Category]]:
        plan = (
            db.query(MonthlyPlan)
            .filter(MonthlyPlan.year == year, MonthlyPlan.month == month)
            .first()
        )
        categories = db.query(Category).filter(Category.is_hidden.is_(False)).order_by(Category.sort_order).all()
        return plan, categories


class DepositService:
    @staticmethod
    def get_current(db: Session) -> tuple[Decimal, Decimal]:
        balance = Decimal(get_setting(db, "deposit_balance", "0"))
        rate = Decimal(get_setting(db, "deposit_rate", "17.5"))
        return balance, rate

    @staticmethod
    def update(db: Session, balance: Decimal, rate: Decimal) -> None:
        set_setting(db, "deposit_balance", str(balance))
        set_setting(db, "deposit_rate", str(rate))

    @staticmethod
    def forecast(
        balance: Decimal,
        rate: Decimal,
        monthly_contribution: Decimal,
        target_date: date,
        start_date: date | None = None,
    ) -> list[tuple[date, Decimal]]:
        start = start_date or date.today()
        monthly_rate = rate / Decimal("100") / Decimal("12")
        current = balance
        points: list[tuple[date, Decimal]] = [(start, current)]
        d = start
        while d <= target_date:
            m = d.month + 1
            y = d.year
            if m > 12:
                m = 1
                y += 1
            d = date(y, m, 1)
            current = current * (1 + monthly_rate) + monthly_contribution
            points.append((d, current.quantize(Decimal("0.01"))))
        return points

    @staticmethod
    def required_monthly(
        balance: Decimal,
        rate: Decimal,
        target: Decimal,
        target_date: date,
    ) -> Decimal:
        start = date.today()
        months = (target_date.year - start.year) * 12 + (target_date.month - start.month)
        if months <= 0:
            return Decimal("0")
        monthly_rate = rate / Decimal("100") / Decimal("12")
        remaining = target - balance
        if monthly_rate == 0:
            return (remaining / months).quantize(Decimal("0.01"))
        factor = ((1 + monthly_rate) ** months - 1) / monthly_rate
        return (remaining / Decimal(str(factor))).quantize(Decimal("0.01"))
