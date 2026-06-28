from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Category, CategoryLimit, MonthlyPlan
from app.seed import GROUP_PERCENTS
from app.services.deposit_calc import (
    build_forecast,
    parse_rate_schedule,
    required_monthly_contribution,
)
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
            categories = (
                db.query(Category)
                .filter(Category.is_hidden.is_(False), Category.group.in_(["needs", "wants", "savings"]))
                .order_by(Category.sort_order)
                .all()
            )
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
        categories = (
            db.query(Category)
            .filter(Category.is_hidden.is_(False), Category.group.in_(["needs", "wants", "savings"]))
            .order_by(Category.sort_order)
            .all()
        )
        return plan, categories

    @staticmethod
    def add_planned_expense(
        db: Session,
        plan_id: int,
        description: str,
        amount: Decimal,
        category_id: int | None = None,
        expected_date: date | None = None,
    ) -> None:
        from app.models import PlannedExpense

        db.add(
            PlannedExpense(
                plan_id=plan_id,
                description=description,
                amount=amount,
                category_id=category_id,
                expected_date=expected_date,
            )
        )
        db.commit()

    @staticmethod
    def add_planned_debt_payment(db: Session, plan_id: int, debt_id: int, amount: Decimal) -> None:
        from app.models import PlannedDebtPayment

        db.add(PlannedDebtPayment(plan_id=plan_id, debt_id=debt_id, amount=amount))
        db.commit()

    @staticmethod
    def delete_planned_expense(db: Session, expense_id: int) -> None:
        from app.models import PlannedExpense

        item = db.query(PlannedExpense).filter(PlannedExpense.id == expense_id).first()
        if item:
            db.delete(item)
            db.commit()

    @staticmethod
    def delete_planned_debt_payment(db: Session, payment_id: int) -> None:
        from app.models import PlannedDebtPayment

        item = db.query(PlannedDebtPayment).filter(PlannedDebtPayment.id == payment_id).first()
        if item:
            db.delete(item)
            db.commit()


class DepositService:
    @staticmethod
    def get_settings(db: Session) -> dict:
        balance = Decimal(get_setting(db, "deposit_balance", "0"))
        rate = Decimal(get_setting(db, "deposit_rate", "17.5"))
        cap_day = int(get_setting(db, "deposit_cap_day", "18") or "18")
        start = get_setting(db, "deposit_start_date", "")
        schedule_raw = get_setting(db, "deposit_rate_schedule", "")
        return {
            "balance": balance,
            "rate": rate,
            "cap_day": cap_day,
            "start_date": date.fromisoformat(start) if start else None,
            "rate_schedule": parse_rate_schedule(schedule_raw, rate),
        }

    @staticmethod
    def get_current(db: Session) -> tuple[Decimal, Decimal]:
        s = DepositService.get_settings(db)
        return s["balance"], s["rate"]

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
        rate_schedule: list | None = None,
        capitalization_day: int | None = None,
        initial_lump_sum: Decimal = Decimal("0"),
    ) -> list[tuple[date, Decimal]]:
        start = start_date or date.today()
        rows = build_forecast(
            start,
            balance,
            rate,
            target_date,
            monthly_contribution,
            initial_lump_sum=initial_lump_sum,
            rate_schedule=rate_schedule,
            capitalization_day=capitalization_day,
        )
        return [(r.date, r.balance_after) for r in rows]

    @staticmethod
    def forecast_detailed(
        db: Session,
        monthly_contribution: Decimal,
        target_date: date,
    ) -> list:
        s = DepositService.get_settings(db)
        start = s["start_date"] or date.today()
        initial_lump = Decimal(get_setting(db, "deposit_initial_lump", "0") or "0")
        # Таблица как в Excel: от даты открытия, стартовый остаток 0, разовый взнос в 1-й месяц
        return build_forecast(
            start,
            Decimal("0"),
            s["rate"],
            target_date,
            monthly_contribution,
            initial_lump_sum=initial_lump,
            rate_schedule=s["rate_schedule"],
            capitalization_day=s["cap_day"],
        )

    @staticmethod
    def forecast_forward(
        db: Session,
        monthly_contribution: Decimal,
        target_date: date,
    ) -> list:
        """Прогноз вперёд от текущего баланса (следующая дата капитализации)."""
        s = DepositService.get_settings(db)
        start = date.today()
        if s["cap_day"]:
            from app.services.deposit_calc import align_capitalization_day, add_months

            cap = align_capitalization_day(start, s["cap_day"])
            if cap <= start:
                start = add_months(cap, 1)
            else:
                start = cap
        return build_forecast(
            start,
            s["balance"],
            s["rate"],
            target_date,
            monthly_contribution,
            rate_schedule=s["rate_schedule"],
            capitalization_day=s["cap_day"],
        )

    @staticmethod
    def required_monthly(
        balance: Decimal,
        rate: Decimal,
        target: Decimal,
        target_date: date,
        start_date: date | None = None,
        rate_schedule: list | None = None,
        capitalization_day: int | None = None,
    ) -> Decimal:
        return required_monthly_contribution(
            balance,
            rate,
            target,
            target_date,
            start_date=start_date,
            rate_schedule=rate_schedule,
            capitalization_day=capitalization_day,
        )
