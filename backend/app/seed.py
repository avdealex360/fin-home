"""Optional demo data + default settings.

Nothing here is created automatically as undeletable. On startup we only ensure
key/value *settings* exist (they are plain config and fully editable). The demo
dataset (categories, debts, funds (копилки)) is loaded only on explicit user
request via the onboarding endpoint.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import AppUser, Category, Debt, Setting, SinkingFund

GROUP_PERCENTS = {"needs": 50, "wants": 30, "savings": 20}

# (name, group, sort_order)
DEMO_CATEGORIES = [
    ("Аренда жилья", "needs", 1),
    ("Продукты и быт", "needs", 2),
    ("Транспорт", "needs", 3),
    ("Здоровье и лекарства", "needs", 4),
    ("Питомец — плановые", "needs", 5),
    ("Питомец — ветеринар", "needs", 6),
    ("Связь и интернет", "needs", 7),
    ("Рассрочка", "needs", 8),
    ("Кредитная карта", "needs", 9),
    ("Рестораны и доставка", "wants", 10),
    ("Подписки и развлечения", "wants", 11),
    ("Одежда и уход", "wants", 12),
    ("Спорт и хобби", "wants", 13),
    ("Подарки", "wants", 14),
    ("Буфер (прочее)", "wants", 15),
    ("Пополнение вклада", "savings", 16),
]

SAVINGS_CATEGORY_NAME = "Пополнение вклада"

DEMO_INCOME_CATEGORIES = [
    ("Зарплата", "income", 101),
    ("Доход партнёра", "income", 102),
    ("Прочие поступления", "income", 103),
]

DEFAULT_SETTINGS = {
    "currency": "RUB",
    "deposit_rate": "17.5",
    "deposit_cap_day": "18",
    "deposit_start_date": "2025-03-18",
    "deposit_term_months": "12",
    "deposit_initial_lump": "0",
    "deposit_rate_schedule": "[]",
    "deposit_monthly_target": "0",
    "ai_primary_provider": "yandex",
    "tg_bot_enabled": "",
    "onboarded": "",  # empty until the user picks demo or clean start
}

DEMO_SINKING_FUNDS = [
    {"name": "Подушка безопасности", "target_amount": Decimal("150000"),
     "monthly_contribution": Decimal("5000"), "target_date": None, "group": "savings", "is_rolling": False},
    {"name": "Отпуск", "target_amount": Decimal("120000"),
     "monthly_contribution": Decimal("8000"),
     "target_date": date(date.today().year, 12, 1), "group": "wants", "is_rolling": False},
    {"name": "Подарки", "target_amount": Decimal("10000"),
     "monthly_contribution": Decimal("1500"),
     "target_date": date(date.today().year, 12, 1), "group": "wants", "is_rolling": True},
]


def ensure_savings_category(db: Session) -> None:
    """Installs seeded before the "Пополнение вклада" category existed (or a
    clean-start setup with categories already created) get it added once it's
    onboarded — деньги, отложенные во вклад, needs a real savings category to
    land in, same as any other expense."""
    if not is_onboarded(db):
        return
    if db.query(Category).filter(Category.name == SAVINGS_CATEGORY_NAME).first():
        return
    if not db.query(Category).first():
        return
    max_order = db.query(Category).count()
    db.add(Category(name=SAVINGS_CATEGORY_NAME, group="savings", sort_order=max_order + 1))
    db.commit()


def ensure_common_user(db: Session) -> None:
    """Installs seeded before the "Общий" (shared) payer existed get it added
    once onboarded — so joint spending (e.g. rent) isn't pinned on one person."""
    if not is_onboarded(db):
        return
    if db.query(AppUser).filter(AppUser.name == "Общий").first():
        return
    if not db.query(AppUser).first():
        return
    db.add(AppUser(name="Общий"))
    db.commit()


def ensure_settings(db: Session) -> None:
    """Insert default config settings if missing. Runs on every startup."""
    changed = False
    for key, value in DEFAULT_SETTINGS.items():
        if not db.query(Setting).filter(Setting.key == key).first():
            db.add(Setting(key=key, value=value))
            changed = True
    if changed:
        db.commit()


def _category_by_name(db: Session, name: str) -> Category | None:
    return db.query(Category).filter(Category.name == name).first()


def is_onboarded(db: Session) -> bool:
    s = db.query(Setting).filter(Setting.key == "onboarded").first()
    return bool(s and s.value)


def _mark_onboarded(db: Session, mode: str) -> None:
    s = db.query(Setting).filter(Setting.key == "onboarded").first()
    if s:
        s.value = mode
    else:
        db.add(Setting(key="onboarded", value=mode))


def load_clean_start(db: Session) -> None:
    """Minimal start: just the family's users. Everything else the user creates."""
    if not db.query(AppUser).first():
        db.add(AppUser(name="Я"))
        db.add(AppUser(name="Партнёр"))
        db.add(AppUser(name="Общий"))
    _mark_onboarded(db, "clean")
    db.commit()


def load_demo_data(db: Session) -> None:
    """Full demo dataset for users who want a populated example to explore."""
    if db.query(Category).first():
        _mark_onboarded(db, "demo")
        db.commit()
        return

    for name, group, order in DEMO_CATEGORIES:
        db.add(Category(name=name, group=group, sort_order=order))
    for name, group, order in DEMO_INCOME_CATEGORIES:
        db.add(Category(name=name, group=group, sort_order=order))

    if not db.query(AppUser).first():
        db.add(AppUser(name="Я"))
        db.add(AppUser(name="Партнёр"))
        db.add(AppUser(name="Общий"))

    db.add(
        Debt(
            name="Кредитная карта",
            total_amount=Decimal("44000"),
            remaining=Decimal("44000"),
            monthly_payment=Decimal("4400"),
            interest_rate=Decimal("29"),
            type="credit_card",
            start_date=date.today(),
            grace_period_end=date(date.today().year, min(date.today().month + 1, 12), 15),
            priority_rank=1,
        )
    )
    db.add(
        Debt(
            name="Рассрочка",
            total_amount=Decimal("92000"),
            remaining=Decimal("92000"),
            monthly_payment=Decimal("23000"),
            interest_rate=Decimal("0"),
            type="split",
            start_date=date.today(),
            next_payment_date=date(date.today().year, min(date.today().month + 1, 12), 1),
            target_close_date=date(date.today().year, min(date.today().month + 4, 12), 1),
            priority_rank=2,
        )
    )

    db.flush()
    for fd in DEMO_SINKING_FUNDS:
        db.add(
            SinkingFund(
                name=fd["name"],
                target_amount=fd["target_amount"],
                current_amount=Decimal("0"),
                monthly_contribution=fd["monthly_contribution"],
                target_date=fd.get("target_date"),
                group=fd["group"],
                is_rolling=fd.get("is_rolling", False),
            )
        )

    _mark_onboarded(db, "demo")
    db.commit()
