from decimal import Decimal

from sqlalchemy import extract, func

from sqlalchemy.orm import Session

from app.models import Transaction
from app.services.settings_store import get_setting


def rub_to_eur(amount_rub: Decimal, eur_rub_rate: Decimal) -> Decimal:
    if eur_rub_rate <= 0:
        return Decimal("0")
    return (amount_rub / eur_rub_rate).quantize(Decimal("0.01"))


def get_eur_rub_rate(db: Session) -> Decimal:
    eur_rub = get_setting(db, "eur_rub_rate", "")
    if eur_rub:
        return Decimal(eur_rub)
    return Decimal("100")


def eur_to_rub(amount_eur: Decimal, eur_rub_rate: Decimal) -> Decimal:
    return (amount_eur * eur_rub_rate).quantize(Decimal("0.01"))


def income_eur_total(db: Session, year: int, month: int) -> Decimal:
    direct = (
        db.query(func.coalesce(func.sum(Transaction.base_amount_eur), 0))
        .filter(
            Transaction.type == "income",
            Transaction.base_amount_eur.isnot(None),
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) == month,
        )
        .scalar()
    )
    return direct or Decimal("0")


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


async def fetch_eur_usd_rate() -> Decimal | None:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://api.frankfurter.app/latest?from=EUR&to=USD")
            resp.raise_for_status()
            rate = resp.json()["rates"]["USD"]
            return Decimal(str(rate)).quantize(Decimal("0.0001"))
    except Exception:
        return None


async def update_eur_usd_rate(db: Session) -> Decimal | None:
    from app.services.settings_store import set_setting

    rate = await fetch_eur_usd_rate()
    if rate is not None:
        set_setting(db, "eur_usd_rate", str(rate))
    return rate
