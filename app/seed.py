from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import AppUser, Category, Debt, Goal, Setting

GROUP_PERCENTS = {"needs": 50, "wants": 30, "savings": 20}

CATEGORIES = [
    ("Аренда жилья", "needs", 1),
    ("Продукты и быт", "needs", 2),
    ("Транспорт", "needs", 3),
    ("Здоровье и лекарства", "needs", 4),
    ("Кот — плановые", "needs", 5),
    ("Кот — ветеринар", "needs", 6),
    ("Связь и интернет", "needs", 7),
    ("Яндекс Сплит", "needs", 8),
    ("Кредитка Тинькофф", "needs", 9),
    ("Рестораны и доставка", "wants", 10),
    ("Подписки и развлечения", "wants", 11),
    ("Одежда и уход", "wants", 12),
    ("Спорт и хобби", "wants", 13),
    ("Подарки", "wants", 14),
    ("Буфер (прочее)", "wants", 15),
    ("Подушка безопасности", "savings", 16),
    ("Вклад (машина)", "savings", 17),
    ("Досрочное погашение долгов", "savings", 18),
]

DEFAULT_SETTINGS = {
    "user1_name": "Пользователь 1",
    "user2_name": "Пользователь 2",
    "currency": "RUB",
    "eur_usd_rate": "1.08",
    "eur_rub_rate": "100",
    "deposit_balance": "0",
    "deposit_rate": "17.5",
    "deposit_cap_day": "18",
    "deposit_start_date": "2025-03-18",
    "deposit_initial_lump": "450000",
    "deposit_rate_schedule": '[{"from":"2025-03-18","rate":"19.5"},{"from":"2026-03-18","rate":"17.5"}]',
    "seed_version": "2",
}

INCOME_CATEGORIES = [
    ("Зарплата", "income", 101),
    ("Доход партнёра", "income", 102),
    ("Прочие поступления", "income", 103),
]


def seed_database(db: Session) -> None:
    existing = db.query(Setting).filter(Setting.key == "seed_version").first()
    if existing and existing.value == "2":
        return

    if not existing:
        for name, group, order in CATEGORIES:
            db.add(Category(name=name, group=group, sort_order=order))
        for name, group, order in INCOME_CATEGORIES:
            db.add(Category(name=name, group=group, sort_order=order))

        db.add(AppUser(name="Пользователь 1"))
        db.add(AppUser(name="Пользователь 2"))

        db.add(
            Debt(
                name="Кредитка Тинькофф",
                total_amount=Decimal("44000"),
                remaining=Decimal("44000"),
                monthly_payment=Decimal("44000"),
                interest_rate=Decimal("29"),
                type="credit_card",
                start_date=date.today(),
            )
        )
        db.add(
            Debt(
                name="Яндекс Сплит",
                total_amount=Decimal("92000"),
                remaining=Decimal("92000"),
                monthly_payment=Decimal("9200"),
                interest_rate=Decimal("0"),
                type="split",
                start_date=date.today(),
            )
        )

        db.add(
            Goal(
                name="Подушка безопасности",
                target_amount=Decimal("150000"),
                current_amount=Decimal("0"),
                monthly_contribution=Decimal("0"),
                linked_account_name="Накопительный счёт",
            )
        )
        db.add(
            Goal(
                name="Машина",
                target_amount=Decimal("1500000"),
                current_amount=Decimal("0"),
                deadline=date(2027, 12, 31),
                monthly_contribution=Decimal("0"),
                linked_account_name="Вклад",
            )
        )
        db.add(
            Goal(
                name="Взнос на квартиру",
                target_amount=Decimal("0"),
                current_amount=Decimal("0"),
                monthly_contribution=Decimal("0"),
            )
        )

        for key, value in DEFAULT_SETTINGS.items():
            db.add(Setting(key=key, value=value))
    else:
        # Migration from seed v1 → v2: add income categories
        for name, group, order in INCOME_CATEGORIES:
            exists = db.query(Category).filter(Category.name == name).first()
            if not exists:
                db.add(Category(name=name, group=group, sort_order=order))
        for key, val in {
            "eur_rub_rate": "100",
            "deposit_cap_day": "18",
            "deposit_start_date": "2025-03-18",
            "deposit_initial_lump": "450000",
            "deposit_rate_schedule": '[{"from":"2025-03-18","rate":"19.5"},{"from":"2026-03-18","rate":"17.5"}]',
        }.items():
            if not db.query(Setting).filter(Setting.key == key).first():
                db.add(Setting(key=key, value=val))
        existing.value = "2"

    db.commit()
