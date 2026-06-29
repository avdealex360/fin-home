from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Category, CategoryLimit, MonthlyPlan
from app.seed import GROUP_PERCENTS
from app.services.settings_store import get_setting, set_setting


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


from app.services.deposit import DepositService  # noqa: E402,F401  (moved; kept for back-compat imports)
