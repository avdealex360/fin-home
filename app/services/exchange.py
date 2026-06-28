from decimal import Decimal

import httpx

from sqlalchemy.orm import Session

from app.services.dashboard import get_setting, set_setting


async def fetch_eur_usd_rate() -> Decimal | None:
    """Fetch EUR/USD from Frankfurter (ECB data, no API key)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://api.frankfurter.app/latest?from=EUR&to=USD")
            resp.raise_for_status()
            rate = resp.json()["rates"]["USD"]
            return Decimal(str(rate)).quantize(Decimal("0.0001"))
    except Exception:
        return None


async def update_eur_usd_rate(db: Session) -> Decimal | None:
    rate = await fetch_eur_usd_rate()
    if rate is not None:
        set_setting(db, "eur_usd_rate", str(rate))
    return rate


def rub_to_eur(amount_rub: Decimal, eur_rub_rate: Decimal) -> Decimal:
    """Convert RUB to EUR using EUR/RUB rate (how many RUB per 1 EUR)."""
    if eur_rub_rate <= 0:
        return Decimal("0")
    return (amount_rub / eur_rub_rate).quantize(Decimal("0.01"))


def get_eur_rub_rate(db: Session) -> Decimal:
    """EUR/RUB rate stored in settings, or derived from eur_usd if only that exists."""
    eur_rub = get_setting(db, "eur_rub_rate", "")
    if eur_rub:
        return Decimal(eur_rub)
    return Decimal("100")


def income_eur_total(db: Session, year: int, month: int) -> Decimal:
    from sqlalchemy import extract, func

    from app.models import Transaction

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
