CATEGORY_ICONS = {
    "Аренда жилья": {"icon": "ti-home", "color": "#5B8DEF"},
    "Продукты и быт": {"icon": "ti-shopping-cart", "color": "#4CAF72"},
    "Транспорт": {"icon": "ti-car", "color": "#5B8DEF"},
    "Здоровье и лекарства": {"icon": "ti-heart-rate-monitor", "color": "#D95F5F"},
    "Кот — плановые": {"icon": "ti-paw", "color": "#C9943A"},
    "Кот — ветеринар": {"icon": "ti-stethoscope", "color": "#D95F5F"},
    "Связь и интернет": {"icon": "ti-wifi", "color": "#8B92A8"},
    "Яндекс Сплит": {"icon": "ti-receipt", "color": "#E0A040"},
    "Кредитка Тинькофф": {"icon": "ti-credit-card", "color": "#D95F5F"},
    "Рестораны и доставка": {"icon": "ti-fork", "color": "#E0A040"},
    "Подписки": {"icon": "ti-brand-netflix", "color": "#5B8DEF"},
    "Одежда и уход": {"icon": "ti-hanger", "color": "#C9943A"},
    "Спорт и хобби": {"icon": "ti-activity", "color": "#4CAF72"},
    "Подарки": {"icon": "ti-gift", "color": "#D95F5F"},
    "Прочее": {"icon": "ti-dots", "color": "#8B92A8"},
    "Подушка": {"icon": "ti-shield", "color": "#4CAF72"},
    "Вклад на машину": {"icon": "ti-building-bank", "color": "#C9943A"},
    "Погашение долгов": {"icon": "ti-arrow-down-circle", "color": "#5B8DEF"},
    "Зарплата": {"icon": "ti-briefcase", "color": "#4CAF72"},
    "Доход партнёра": {"icon": "ti-briefcase", "color": "#4CAF72"},
    "Прочий доход": {"icon": "ti-plus-circle", "color": "#4CAF72"},
}

_DEFAULT = {"icon": "ti-dots", "color": "#8B92A8"}


def get_category_icon(name: str) -> dict:
    return CATEGORY_ICONS.get(name, _DEFAULT)
