from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import AppUser, Category, Debt, Goal, Setting, SinkingFund

GROUP_PERCENTS = {"needs": 50, "wants": 30, "savings": 20}

# allocation_level: 1=obligations, 2=variable needs, 4=wants+savings (3=sinking funds)
CATEGORIES = [
    ("Аренда жилья", "needs", 1, 1),
    ("Продукты и быт", "needs", 2, 2),
    ("Транспорт", "needs", 3, 2),
    ("Здоровье и лекарства", "needs", 4, 2),
    ("Кот — плановые", "needs", 5, 2),
    ("Кот — ветеринар", "needs", 6, 2),
    ("Связь и интернет", "needs", 7, 1),
    ("Яндекс Сплит", "needs", 8, 1),
    ("Кредитка Тинькофф", "needs", 9, 1),
    ("Рестораны и доставка", "wants", 10, 4),
    ("Подписки и развлечения", "wants", 11, 4),
    ("Одежда и уход", "wants", 12, 4),
    ("Спорт и хобби", "wants", 13, 4),
    ("Подарки", "wants", 14, 4),
    ("Буфер (прочее)", "wants", 15, 4),
    ("Подушка безопасности", "savings", 16, 4),
    ("Вклад (машина)", "savings", 17, 4),
    ("Досрочное погашение долгов", "savings", 18, 4),
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
    "seed_version": "3",
}

INCOME_CATEGORIES = [
    ("Зарплата", "income", 101),
    ("Доход партнёра", "income", 102),
    ("Прочие поступления", "income", 103),
]

SINKING_FUNDS = [
    {
        "name": "Ветеринар — операция кота",
        "target_amount": Decimal("30000"),
        "monthly_contribution": Decimal("10000"),
        "target_date": date(2026, 9, 1),
        "category_group": "needs",
        "linked_category_name": "Кот — ветеринар",
    },
    {
        "name": "Ветеринар — плановый",
        "target_amount": Decimal("5000"),
        "monthly_contribution": Decimal("1700"),
        "target_date": None,
        "category_group": "needs",
        "linked_category_name": "Кот — ветеринар",
        "is_rolling": True,
    },
    {
        "name": "Подарки",
        "target_amount": Decimal("10000"),
        "monthly_contribution": Decimal("1500"),
        "target_date": date(2026, 12, 1),
        "category_group": "wants",
        "linked_category_name": "Подарки",
    },
]


def _category_by_name(db: Session, name: str) -> Category | None:
    return db.query(Category).filter(Category.name == name).first()


def seed_database(db: Session) -> None:
    existing = db.query(Setting).filter(Setting.key == "seed_version").first()
    if existing and existing.value == "3":
        return

    if not existing:
        for name, group, order, level in CATEGORIES:
            db.add(Category(name=name, group=group, sort_order=order, allocation_level=level))
        for name, group, order in INCOME_CATEGORIES:
            db.add(Category(name=name, group=group, sort_order=order))

        db.add(AppUser(name="Пользователь 1"))
        db.add(AppUser(name="Пользователь 2"))

        db.add(
            Debt(
                name="Кредитка Тинькофф",
                total_amount=Decimal("44000"),
                remaining=Decimal("44000"),
                monthly_payment=Decimal("4400"),
                interest_rate=Decimal("29"),
                type="credit_card",
                start_date=date.today(),
                grace_period_end=date(2026, 7, 15),
                priority_rank=1,
            )
        )
        db.add(
            Debt(
                name="Яндекс Сплит",
                total_amount=Decimal("92000"),
                remaining=Decimal("92000"),
                monthly_payment=Decimal("23000"),
                interest_rate=Decimal("0"),
                type="split",
                start_date=date.today(),
                next_payment_date=date(2026, 7, 1),
                target_close_date=date(2026, 10, 1),
                priority_rank=2,
            )
        )

        db.flush()
        pillow = _category_by_name(db, "Подушка безопасности")
        car = _category_by_name(db, "Вклад (машина)")

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
                name="Машина",
                target_amount=Decimal("1500000"),
                current_amount=Decimal("0"),
                deadline=date(2027, 12, 31),
                monthly_contribution=Decimal("0"),
                linked_account_name="Вклад",
                linked_category_id=car.id if car else None,
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

        db.flush()
        _seed_sinking_funds(db)
    elif existing and existing.value == "2":
        for name, group, order, level in CATEGORIES:
            cat = db.query(Category).filter(Category.name == name).first()
            if cat:
                cat.allocation_level = level
            else:
                db.add(Category(name=name, group=group, sort_order=order, allocation_level=level))

        for name, group, order in INCOME_CATEGORIES:
            exists = db.query(Category).filter(Category.name == name).first()
            if not exists:
                db.add(Category(name=name, group=group, sort_order=order))

        credit = db.query(Debt).filter(Debt.name == "Кредитка Тинькофф").first()
        if credit:
            credit.monthly_payment = Decimal("4400")
            credit.grace_period_end = date(2026, 7, 15)
            credit.priority_rank = 1

        split = db.query(Debt).filter(Debt.name == "Яндекс Сплит").first()
        if split:
            split.monthly_payment = Decimal("23000")
            split.next_payment_date = date(2026, 7, 1)
            split.target_close_date = date(2026, 10, 1)
            split.priority_rank = 2

        pillow = _category_by_name(db, "Подушка безопасности")
        car = _category_by_name(db, "Вклад (машина)")
        pillow_goal = db.query(Goal).filter(Goal.name == "Подушка безопасности").first()
        if pillow_goal and pillow:
            pillow_goal.linked_category_id = pillow.id
        car_goal = db.query(Goal).filter(Goal.name == "Машина").first()
        if car_goal and car:
            car_goal.linked_category_id = car.id

        for key, val in {
            "eur_rub_rate": "100",
            "deposit_cap_day": "18",
            "deposit_start_date": "2025-03-18",
            "deposit_initial_lump": "450000",
            "deposit_rate_schedule": '[{"from":"2025-03-18","rate":"19.5"},{"from":"2026-03-18","rate":"17.5"}]',
        }.items():
            if not db.query(Setting).filter(Setting.key == key).first():
                db.add(Setting(key=key, value=val))

        _seed_sinking_funds(db)
        existing.value = "3"

    db.commit()


def _seed_sinking_funds(db: Session) -> None:
    for fund_data in SINKING_FUNDS:
        exists = db.query(SinkingFund).filter(SinkingFund.name == fund_data["name"]).first()
        if exists:
            continue
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
