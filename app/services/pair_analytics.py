from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models import AppUser, Category, Transaction


@dataclass
class UserSpending:
    user_id: int
    user_name: str
    total: Decimal
    top_category: str | None
    top_amount: Decimal


@dataclass
class PairAnalytics:
    users: list[UserSpending]
    month_total: Decimal


class PairAnalyticsService:
    @staticmethod
    def monthly_breakdown(db: Session, year: int, month: int) -> PairAnalytics:
        users = db.query(AppUser).filter(AppUser.is_active.is_(True)).all()
        result_users: list[UserSpending] = []

        month_total = (
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.type == "expense",
                extract("year", Transaction.date) == year,
                extract("month", Transaction.date) == month,
            )
            .scalar()
        ) or Decimal("0")

        for user in users:
            total = (
                db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .filter(
                    Transaction.type == "expense",
                    Transaction.user_id == user.id,
                    extract("year", Transaction.date) == year,
                    extract("month", Transaction.date) == month,
                )
                .scalar()
            ) or Decimal("0")

            top_row = (
                db.query(
                    Category.name,
                    func.sum(Transaction.amount).label("amt"),
                )
                .join(Category, Transaction.category_id == Category.id)
                .filter(
                    Transaction.type == "expense",
                    Transaction.user_id == user.id,
                    extract("year", Transaction.date) == year,
                    extract("month", Transaction.date) == month,
                )
                .group_by(Category.name)
                .order_by(func.sum(Transaction.amount).desc())
                .first()
            )

            result_users.append(
                UserSpending(
                    user_id=user.id,
                    user_name=user.name,
                    total=total,
                    top_category=top_row[0] if top_row else None,
                    top_amount=top_row[1] if top_row else Decimal("0"),
                )
            )

        return PairAnalytics(users=result_users, month_total=month_total)

    @staticmethod
    def category_average_for_user(
        db: Session, user_id: int, category_id: int, months: int = 3
    ) -> Decimal | None:
        from datetime import date

        today = date.today()
        totals = []
        y, m = today.year, today.month
        for _ in range(months):
            spent = (
                db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .filter(
                    Transaction.type == "expense",
                    Transaction.user_id == user_id,
                    Transaction.category_id == category_id,
                    extract("year", Transaction.date) == y,
                    extract("month", Transaction.date) == m,
                )
                .scalar()
            ) or Decimal("0")
            totals.append(spent)
            if m == 1:
                y, m = y - 1, 12
            else:
                m -= 1
        if not totals:
            return None
        return sum(totals) / len(totals)
