CATEGORY_ICONS = {
    # Нужды
    "Аренда жилья": {"icon": "ti-home", "color": "#5B8DEF"},
    "Продукты и быт": {"icon": "ti-shopping-cart", "color": "#4CAF72"},
    "Транспорт": {"icon": "ti-car", "color": "#5B8DEF"},
    "Здоровье и лекарства": {"icon": "ti-heart-rate-monitor", "color": "#D95F5F"},
    "Питомец — плановые": {"icon": "ti-paw", "color": "#C9943A"},
    "Питомец — ветеринар": {"icon": "ti-stethoscope", "color": "#D95F5F"},
    "Связь и интернет": {"icon": "ti-wifi", "color": "#8B92A8"},
    "Рассрочка": {"icon": "ti-receipt", "color": "#E0A040"},
    "Кредитная карта": {"icon": "ti-credit-card", "color": "#D95F5F"},
    # legacy needs names (pre-redesign DBs)
    "Кот — плановые": {"icon": "ti-paw", "color": "#C9943A"},
    "Кот — ветеринар": {"icon": "ti-stethoscope", "color": "#D95F5F"},
    "Яндекс Сплит": {"icon": "ti-receipt", "color": "#E0A040"},
    "Кредитка Тинькофф": {"icon": "ti-credit-card", "color": "#D95F5F"},
    # Желания
    "Рестораны и доставка": {"icon": "ti-tools-kitchen-2", "color": "#E0A040"},
    "Подписки и развлечения": {"icon": "ti-device-tv", "color": "#5B8DEF"},
    "Одежда и уход": {"icon": "ti-hanger", "color": "#C9943A"},
    "Спорт и хобби": {"icon": "ti-activity", "color": "#4CAF72"},
    "Подарки": {"icon": "ti-gift", "color": "#D95F5F"},
    "Буфер (прочее)": {"icon": "ti-inbox", "color": "#8B92A8"},
    # legacy wants names
    "Подписки": {"icon": "ti-brand-netflix", "color": "#5B8DEF"},
    "Прочее": {"icon": "ti-inbox", "color": "#8B92A8"},
    # Сбережения
    "Подушка": {"icon": "ti-shield", "color": "#4CAF72"},
    "Вклад на машину": {"icon": "ti-building-bank", "color": "#C9943A"},
    "Погашение долгов": {"icon": "ti-arrow-down-circle", "color": "#5B8DEF"},
    # Доход
    "Зарплата": {"icon": "ti-briefcase", "color": "#4CAF72"},
    "Доход партнёра": {"icon": "ti-briefcase", "color": "#4CAF72"},
    "Прочие поступления": {"icon": "ti-circle-plus", "color": "#4CAF72"},
    # legacy income names
    "Прочий доход": {"icon": "ti-circle-plus", "color": "#4CAF72"},
}

_GROUP_DEFAULTS = {
    "needs": {"icon": "ti-wallet", "color": "#5B8DEF"},
    "wants": {"icon": "ti-sparkles", "color": "#E0A040"},
    "savings": {"icon": "ti-pig-money", "color": "#4CAF72"},
    "income": {"icon": "ti-cash", "color": "#4CAF72"},
}

_FALLBACK = {"icon": "ti-tag", "color": "#8B92A8"}


def get_category_icon(name: str, group: str | None = None) -> dict:
    if name in CATEGORY_ICONS:
        return CATEGORY_ICONS[name]
    if group and group in _GROUP_DEFAULTS:
        return _GROUP_DEFAULTS[group]
    return _FALLBACK
