"""Optional demo data + default settings.

Nothing here is created automatically as undeletable. On startup we only ensure
key/value *settings* exist (they are plain config and fully editable). The demo
dataset (categories, debts, goals, funds) is loaded only on explicit user
request via the onboarding endpoint.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import AppUser, Category, Debt, Setting, SinkingFund  # Goal removed in two-pots redesign (Task 1)

GROUP_PERCENTS = {"needs": 50, "wants": 30, "savings": 20}

# allocation_level: 1=obligations, 2=variable needs, 4=wants+savings (3=sinking funds)
DEMO_CATEGORIES = [
    ("Аренда жилья", "needs", 1, 1),
    ("Продукты и быт", "needs", 2, 2),
    ("Транспорт", "needs", 3, 2),
    ("Здоровье и лекарства", "needs", 4, 2),
    ("Питомец — плановые", "needs", 5, 2),
    ("Питомец — ветеринар", "needs", 6, 2),
    ("Связь и интернет", "needs", 7, 1),
    ("Рассрочка", "needs", 8, 1),
    ("Кредитная карта", "needs", 9, 1),
    ("Рестораны и доставка", "wants", 10, 4),
    ("Подписки и развлечения", "wants", 11, 4),
    ("Одежда и уход", "wants", 12, 4),
    ("Спорт и хобби", "wants", 13, 4),
    ("Подарки", "wants", 14, 4),
    ("Буфер (прочее)", "wants", 15, 4),
    ("Подушка безопасности", "savings", 16, 4),
    ("Вклад (крупная цель)", "savings", 17, 4),
    ("Досрочное погашение долгов", "savings", 18, 4),
]

DEMO_INCOME_CATEGORIES = [
    ("Зарплата", "income", 101),
    ("Доход партнёра", "income", 102),
    ("Прочие поступления", "income", 103),
]

DEFAULT_SETTINGS = {
    "user1_name": "Я",
    "user2_name": "Партнёр",
    "currency": "RUB",
    "eur_usd_rate": "1.08",
    "eur_rub_rate": "100",
    "deposit_balance": "0",
    "deposit_rate": "17.5",
    "deposit_cap_day": "18",
    "deposit_start_date": "2025-03-18",
    "deposit_initial_lump": "0",
    "deposit_rate_schedule": "[]",
    "onboarded": "",  # empty until the user picks demo or clean start
}

DEMO_SINKING_FUNDS = [
    {
        "name": "Ветеринар — операция",
        "target_amount": Decimal("30000"),
        "monthly_contribution": Decimal("10000"),
        "target_date": date(date.today().year, min(date.today().month + 3, 12), 1),
        "category_group": "needs",
        "linked_category_name": "Питомец — ветеринар",
    },
    {
        "name": "Ветеринар — плановый",
        "target_amount": Decimal("5000"),
        "monthly_contribution": Decimal("1700"),
        "target_date": None,
        "category_group": "needs",
        "linked_category_name": "Питомец — ветеринар",
        "is_rolling": True,
    },
    {
        "name": "Подарки",
        "target_amount": Decimal("10000"),
        "monthly_contribution": Decimal("1500"),
        "target_date": date(date.today().year, 12, 1),
        "category_group": "wants",
        "linked_category_name": "Подарки",
    },
]


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
    """Minimal start: just two users. Everything else the user creates."""
    if not db.query(AppUser).first():
        db.add(AppUser(name="Я"))
        db.add(AppUser(name="Партнёр"))
    _mark_onboarded(db, "clean")
    db.commit()


def load_demo_data(db: Session) -> None:
    """Full demo dataset for users who want a populated example to explore."""
    if db.query(Category).first():
        _mark_onboarded(db, "demo")
        db.commit()
        return

    for name, group, order, level in DEMO_CATEGORIES:
        db.add(Category(name=name, group=group, sort_order=order, allocation_level=level))
    for name, group, order in DEMO_INCOME_CATEGORIES:
        db.add(Category(name=name, group=group, sort_order=order))

    if not db.query(AppUser).first():
        db.add(AppUser(name="Я"))
        db.add(AppUser(name="Партнёр"))

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
    pillow = _category_by_name(db, "Подушка безопасности")
    big = _category_by_name(db, "Вклад (крупная цель)")

    db.add(
        Goal(
            name="Подушка безопасности",
            target_amount=Decimal("150000"),
            current_amount=Decimal("0"),
            monthly_contribution=Decimal("0"),
            linked_account_name="Накопительный счёт",
            linked_category_id=pillow.id if pillow else None,
        )
    )
    db.add(
        Goal(
            name="Крупная цель",
            target_amount=Decimal("1500000"),
            current_amount=Decimal("0"),
            deadline=date(date.today().year + 2, 12, 31),
            monthly_contribution=Decimal("0"),
            linked_account_name="Вклад",
            linked_category_id=big.id if big else None,
        )
    )

    db.flush()
    for fund_data in DEMO_SINKING_FUNDS:
        linked = _category_by_name(db, fund_data["linked_category_name"])
        db.add(
            SinkingFund(
                name=fund_data["name"],
                target_amount=fund_data["target_amount"],
                current_amount=Decimal("0"),
                monthly_contribution=fund_data["monthly_contribution"],
                target_date=fund_data.get("target_date"),
                category_group=fund_data["category_group"],
                is_rolling=fund_data.get("is_rolling", False),
                linked_category_id=linked.id if linked else None,
            )
        )

    _mark_onboarded(db, "demo")
    db.commit()
