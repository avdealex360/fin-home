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


templates.env.filters["money"] = _format_money
templates.env.globals["month_name"] = lambda m: MONTH_NAMES[m] if 1 <= m <= 12 else str(m)
templates.env.globals["now_date"] = date.today
