"""Shared helpers with no framework dependencies."""

from calendar import monthrange
from datetime import date

MONTH_NAMES = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]

MONTH_NAMES_SHORT = [
    "", "янв", "фев", "мар", "апр", "мая", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек",
]


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    m = month + delta
    y = year
    while m < 1:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return y, m


# Backwards-compatible alias used across services.
_shift_month = shift_month


def month_name(m: int) -> str:
    return MONTH_NAMES[m] if 1 <= m <= 12 else str(m)


def period_date_range(year: int, month: int, period: str) -> tuple[date, date]:
    """Inclusive [start, end] date range for 'month' | 'quarter' | 'year',
    anchored on the given year/month."""
    if period == "year":
        return date(year, 1, 1), date(year, 12, 31)
    if period == "quarter":
        q_start_month = (month - 1) // 3 * 3 + 1
        q_end_month = q_start_month + 2
        return date(year, q_start_month, 1), date(year, q_end_month, monthrange(year, q_end_month)[1])
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def months_in_range(start: date, end: date) -> list[tuple[int, int]]:
    """List of (year, month) pairs covered by an inclusive date range."""
    pairs = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        pairs.append((y, m))
        y, m = shift_month(y, m, 1)
    return pairs
