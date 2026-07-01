from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models import Transaction


def last_month_salary_rub(db: Session, year: int, month: int) -> Decimal | None:
    from app.util import _shift_month

    prev_year, prev_month = _shift_month(year, month, -1)
    from app.models import Category

    salary_cat = db.query(Category).filter(Category.name == "Зарплата").first()
    if not salary_cat:
        return None
    result = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.type == "income",
            Transaction.category_id == salary_cat.id,
            extract("year", Transaction.date) == prev_year,
            extract("month", Transaction.date) == prev_month,
        )
        .scalar()
    )
    return result if result and result > 0 else None


def salary_comparison(
    db: Session, year: int, month: int, current_rub: Decimal
) -> tuple[Decimal | None, Decimal | None]:
    """Returns (last_month_rub, diff) where diff = current - last."""
    last = last_month_salary_rub(db, year, month)
    if last is None:
        return None, None
    return last, current_rub - last
