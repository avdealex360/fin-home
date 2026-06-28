from datetime import date

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

MONTH_NAMES = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]


def _format_money(value) -> str:
    if value is None:
        return "0"
    return f"{float(value):,.0f}".replace(",", " ")


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    m = month + delta
    y = year
    while m < 1:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return y, m


templates.env.filters["money"] = _format_money
templates.env.globals["month_name"] = lambda m: MONTH_NAMES[m] if 1 <= m <= 12 else str(m)
templates.env.globals["now_date"] = date.today
templates.env.globals["shift_month"] = _shift_month
