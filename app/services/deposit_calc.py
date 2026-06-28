from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


@dataclass
class DepositForecastRow:
    date: date
    balance_before: Decimal
    contribution: Decimal
    rate: Decimal
    interest: Decimal
    balance_after: Decimal


def monthly_interest(base: Decimal, annual_rate: Decimal) -> Decimal:
    if base <= 0 or annual_rate <= 0:
        return Decimal("0")
    monthly = annual_rate / Decimal("100") / Decimal("12")
    return (base * monthly).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def deposit_step(
    balance: Decimal, annual_rate: Decimal, contribution: Decimal = Decimal("0")
) -> tuple[Decimal, Decimal]:
    """Как в Excel: (остаток + взнос) + проценты на эту сумму."""
    base = balance + contribution
    interest = monthly_interest(base, annual_rate)
    return base + interest, interest


def parse_rate_schedule(raw: str, default_rate: Decimal) -> list[tuple[date, Decimal]]:
    import json

    if not raw or not raw.strip():
        return [(date(1900, 1, 1), default_rate)]
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return [(date(1900, 1, 1), default_rate)]
    schedule = [(date.fromisoformat(item["from"]), Decimal(str(item["rate"]))) for item in items]
    schedule.sort(key=lambda x: x[0])
    return schedule


def rate_on_date(d: date, schedule: list[tuple[date, Decimal]], fallback: Decimal) -> Decimal:
    rate = fallback
    for from_date, r in schedule:
        if d >= from_date:
            rate = r
    return rate


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def add_months(d: date, months: int = 1) -> date:
    m = d.month + months
    y = d.year
    while m > 12:
        m -= 12
        y += 1
    day = min(d.day, _days_in_month(y, m))
    return date(y, m, day)


def align_capitalization_day(d: date, cap_day: int) -> date:
    cap_day = max(1, min(28, cap_day))
    return date(d.year, d.month, min(cap_day, _days_in_month(d.year, d.month)))


def build_forecast(
    start_date: date,
    initial_balance: Decimal,
    annual_rate: Decimal,
    target_date: date,
    monthly_contribution: Decimal = Decimal("0"),
    *,
    initial_lump_sum: Decimal = Decimal("0"),
    rate_schedule: list[tuple[date, Decimal]] | None = None,
    capitalization_day: int | None = None,
) -> list[DepositForecastRow]:
    schedule = rate_schedule or [(date(1900, 1, 1), annual_rate)]
    rows: list[DepositForecastRow] = []
    balance = initial_balance
    d = align_capitalization_day(start_date, capitalization_day) if capitalization_day else start_date

    while d <= target_date:
        rate = rate_on_date(d, schedule, annual_rate)
        if not rows:
            contrib = initial_lump_sum if initial_lump_sum > 0 else monthly_contribution
        else:
            contrib = monthly_contribution

        before = balance
        after, interest = deposit_step(balance, rate, contrib)
        rows.append(
            DepositForecastRow(
                date=d,
                balance_before=before,
                contribution=contrib,
                rate=rate,
                interest=interest,
                balance_after=after,
            )
        )
        balance = after
        d = add_months(d, 1)

    return rows


def required_monthly_contribution(
    current_balance: Decimal,
    annual_rate: Decimal,
    target: Decimal,
    target_date: date,
    start_date: date | None = None,
    rate_schedule: list[tuple[date, Decimal]] | None = None,
    capitalization_day: int | None = None,
) -> Decimal:
    start = start_date or date.today()
    if current_balance >= target:
        return Decimal("0")

    lo, hi = Decimal("0"), target
    for _ in range(60):
        mid = ((lo + hi) / 2).quantize(Decimal("0.01"))
        rows = build_forecast(
            start,
            current_balance,
            annual_rate,
            target_date,
            mid,
            rate_schedule=rate_schedule,
            capitalization_day=capitalization_day,
        )
        final = rows[-1].balance_after if rows else current_balance
        if final >= target:
            hi = mid
        else:
            lo = mid
    return hi.quantize(Decimal("0.01"))
