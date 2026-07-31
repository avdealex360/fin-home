"""Optional demo data + default settings, all workspace-scoped.

Nothing here is created automatically as undeletable. On startup we only ensure
key/value *settings* exist (they are plain config and fully editable). The demo
dataset (categories, debts, funds (копилки)) is loaded only on explicit user
request via the onboarding endpoint.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Account, AppUser, Category, Debt, Setting, SinkingFund, Workspace

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

# Per-workspace config, created for every new workspace. Deposit values are
# neutral placeholders — the user sets their own in the calculator.
DEFAULT_WORKSPACE_SETTINGS = {
    "currency": "RUB",
    "deposit_rate": "16",
    "deposit_cap_day": "1",
    "deposit_start_date": "",
    "deposit_term_months": "12",
    "deposit_initial_lump": "0",
    "deposit_rate_schedule": "[]",
    "deposit_monthly_target": "0",
}

# Install-wide config (workspace_id NULL): one Telegram bot / AI account.
DEFAULT_GLOBAL_SETTINGS = {
    "ai_primary_provider": "yandex",
    "tg_bot_enabled": "",
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


def ensure_admin_account(db: Session) -> None:
    """Bootstrap: with no accounts at all, create the admin from APP_USER /
    APP_PASSWORD_HASH env so the existing login keeps working after the
    multi-tenancy deploy with zero manual steps."""
    from app.config import get_settings

    if db.query(Account).first():
        return
    settings = get_settings()
    password_hash = settings.app_password_hash
    if not password_hash and settings.app_password:
        from app.services.auth import hash_password

        password_hash = hash_password(settings.app_password)
    if not settings.app_user or not password_hash:
        return
    workspace = db.query(Workspace).order_by(Workspace.id).first()
    if not workspace:
        workspace = Workspace(name="Семья")
        db.add(workspace)
        db.flush()
    db.add(
        Account(
            username=settings.app_user,
            password_hash=password_hash,
            workspace_id=workspace.id,
            is_admin=True,
        )
    )
    db.commit()


def ensure_startup_data(db: Session) -> None:
    """Idempotent per-startup backfills: settings for every scope + legacy
    installs get the savings category and the shared payer."""
    ensure_global_settings(db)
    for ws in db.query(Workspace).all():
        ensure_workspace_settings(db, ws.id)
        ensure_savings_category(db, ws.id)
        ensure_common_user(db, ws.id)


def ensure_savings_category(db: Session, ws_id: int) -> None:
    """Installs seeded before the "Пополнение вклада" category existed (or a
    clean-start setup with categories already created) get it added once it's
    onboarded — деньги, отложенные во вклад, needs a real savings category to
    land in, same as any other expense."""
    if not is_onboarded(db, ws_id):
        return
    q = db.query(Category).filter(Category.workspace_id == ws_id)
    if q.filter(Category.name == SAVINGS_CATEGORY_NAME).first():
        return
    if not q.first():
        return
    max_order = q.count()
    db.add(Category(workspace_id=ws_id, name=SAVINGS_CATEGORY_NAME, group="savings", sort_order=max_order + 1))
    db.commit()


def ensure_common_user(db: Session, ws_id: int) -> None:
    """Installs seeded before the "Общий" (shared) payer existed get it added
    once onboarded — so joint spending (e.g. rent) isn't pinned on one person."""
    if not is_onboarded(db, ws_id):
        return
    q = db.query(AppUser).filter(AppUser.workspace_id == ws_id)
    if q.filter(AppUser.name == "Общий").first():
        return
    if not q.first():
        return
    db.add(AppUser(workspace_id=ws_id, name="Общий"))
    db.commit()


def ensure_workspace_settings(db: Session, ws_id: int) -> None:
    """Insert missing per-workspace config defaults."""
    changed = False
    for key, value in DEFAULT_WORKSPACE_SETTINGS.items():
        if not db.query(Setting).filter(Setting.workspace_id == ws_id, Setting.key == key).first():
            db.add(Setting(workspace_id=ws_id, key=key, value=value))
            changed = True
    if changed:
        db.commit()


def ensure_global_settings(db: Session) -> None:
    """Insert missing install-wide config defaults (workspace_id NULL)."""
    changed = False
    for key, value in DEFAULT_GLOBAL_SETTINGS.items():
        if not db.query(Setting).filter(Setting.workspace_id.is_(None), Setting.key == key).first():
            db.add(Setting(workspace_id=None, key=key, value=value))
            changed = True
    if changed:
        db.commit()


def is_onboarded(db: Session, ws_id: int) -> bool:
    ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
    return bool(ws and ws.onboarded)


def _mark_onboarded(db: Session, ws_id: int, mode: str) -> None:
    ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
    if ws:
        ws.onboarded = mode


def load_clean_start(db: Session, ws_id: int) -> None:
    """Minimal start: just the family's users. Everything else the user creates."""
    if not db.query(AppUser).filter(AppUser.workspace_id == ws_id).first():
        db.add(AppUser(workspace_id=ws_id, name="Я"))
        db.add(AppUser(workspace_id=ws_id, name="Партнёр"))
        db.add(AppUser(workspace_id=ws_id, name="Общий"))
    _mark_onboarded(db, ws_id, "clean")
    db.commit()


def load_demo_data(db: Session, ws_id: int) -> None:
    """Full demo dataset for users who want a populated example to explore."""
    if db.query(Category).filter(Category.workspace_id == ws_id).first():
        _mark_onboarded(db, ws_id, "demo")
        db.commit()
        return

    for name, group, order in DEMO_CATEGORIES:
        db.add(Category(workspace_id=ws_id, name=name, group=group, sort_order=order))
    for name, group, order in DEMO_INCOME_CATEGORIES:
        db.add(Category(workspace_id=ws_id, name=name, group=group, sort_order=order))

    if not db.query(AppUser).filter(AppUser.workspace_id == ws_id).first():
        db.add(AppUser(workspace_id=ws_id, name="Я"))
        db.add(AppUser(workspace_id=ws_id, name="Партнёр"))
        db.add(AppUser(workspace_id=ws_id, name="Общий"))

    db.add(
        Debt(
            workspace_id=ws_id,
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
            workspace_id=ws_id,
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
                workspace_id=ws_id,
                name=fd["name"],
                target_amount=fd["target_amount"],
                current_amount=Decimal("0"),
                monthly_contribution=fd["monthly_contribution"],
                target_date=fd.get("target_date"),
                group=fd["group"],
                is_rolling=fd.get("is_rolling", False),
            )
        )

    _mark_onboarded(db, ws_id, "demo")
    db.commit()
