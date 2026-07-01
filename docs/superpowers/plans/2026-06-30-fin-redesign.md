# fin-home Radical Redesign — Implementation Plan

> **Статус:** ✅ выполнен (v3). Актуальная документация: [PROJECT.md](../../PROJECT.md) · [README.md](../../../README.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перестроить fin-home в ясную модель «двух потов» (расходуемые Копилки + замороженный Вклад), сделать сквозной флоу 50/30/20 видимым на всех экранах, переписать автораспределение и добавить раздел FAQ.

**Architecture:** Бэкенд (FastAPI + SQLAlchemy + SQLite) — сначала пересобираем модель данных и доменные сервисы под TDD (pytest, in-memory SQLite). Затем фронтенд (Svelte 5 PWA) переписываем под новый JSON-контракт, проверяя каждый экран в Vite preview. FAQ — статический Svelte-компонент без бэкенда.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, pytest; Svelte 5 (runes), Vite, TypeScript, Chart.js.

## Global Constraints

- **Данные не мигрируем** — приложением ещё не пользовались. Схему пересоздаём; для прода добавляем одну alembic-ревизию, которая дропает и заново создаёт затронутые таблицы.
- **Два пота:** «Копилка» (внутреннее имя модели `SinkingFund`, в UI «Копилка») — расходуемый конверт; «Вклад» — замороженный, баланс только растёт.
- **`Goal`/`GoalContribution` удаляются полностью.**
- **Категории группы `savings` как расходные удаляются** — сбережения уходят во Вклад / savings-копилки.
- **`Category.group` принимает только** `needs` | `wants` | `income`. **Копилка.group принимает только** `wants` | `savings`.
- **Контракт TS↔Python:** `frontend/src/lib/api.ts` ↔ `backend/app/serializers.py` держим синхронно.
- **UI на русском, mobile-first, дизайн-токены из `frontend/src/app.css`.** Иконки — Tabler (`ti ti-*`).
- **Тесты бэкенда:** `cd backend && .venv/bin/pytest`. Фикстура `db` (in-memory SQLite + `seed`) — образец в `backend/tests/test_v2.py`.
- **Каждый таск заканчивается коммитом.** Сообщения коммитов в стиле `feat:`/`refactor:`/`test:`.

---

## File Structure

**Backend**
- `app/models/__init__.py` — упростить `SinkingFund` (поле `group`), удалить `Goal`/`GoalContribution`, добавить `DepositContribution`, добавить `IncomeAllocation.to_deposit`.
- `app/seed.py` — категории только needs/wants/income, демо-копилки (wants+savings), новый сеттинг `deposit_monthly_target`, без savings-категорий и без Goal.
- `app/services/deposit.py` — **новый** сервис вклада (баланс, пополнение, журнал, monthly_target). (Сейчас `DepositService` живёт в `services/plan.py` — выносим в свой файл.)
- `app/services/sinking_funds.py` — `category_group` → `group`, `FundSummary.group`.
- `app/services/allocation.py` — три корзины 50/30/20, авто-заполнение по плану, адресат «вклад».
- `app/services/dashboard.py` — корзина savings = вклад + savings-копилки; удалить `Goal`; цель savings %.
- `app/services/analytics.py` — блок «факт 50/30/20».
- `app/services/plan.py` — данные 50/30/20-метра + «подогнать».
- `app/serializers.py` — `fund_dict.group`, удалить `goal_dict`/`goal_contribution_dict`, новый `deposit_dict`.
- `app/api/funds.py`, `app/api/deposit.py`, `app/api/allocation.py`, `app/api/plan.py`, `app/api/analytics.py` — под новый контракт; **удалить** `app/api/goals.py` и его подключение в `main.py`.
- `alembic/versions/<rev>_redesign_reset.py` — reset затронутых таблиц.
- `tests/test_redesign.py` — **новый** файл тестов фазы 1.

**Frontend**
- `src/lib/api.ts` — типы и методы под новый контракт.
- `src/lib/components/AllocationSheet.svelte` — три корзины.
- `src/lib/components/TxForm.svelte` — группировка категорий + остаток корзины.
- `src/lib/components/Onboarding.svelte` — ссылка на FAQ, тексты под новую модель.
- `src/routes/Plan.svelte` — 50/30/20-метр + «подогнать».
- `src/routes/Deposit.svelte` — «пополнить», баланс только растёт, журнал.
- `src/routes/Analytics.svelte` — блок «факт 50/30/20».
- `src/routes/Dashboard.svelte` — подписи целей %.
- `src/routes/More.svelte` — копилки с целью (бывшие «Цели» убраны), без отдельной секции целей.
- `src/routes/Faq.svelte` — **новый** раздел FAQ.
- `src/lib/components/BottomNav.svelte` / `src/routes/More.svelte` — вход в FAQ.

---

# PHASE 1 — Backend foundation (TDD)

### Task 1: Reset data model

**Files:**
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_redesign.py`

**Interfaces:**
- Produces:
  - `SinkingFund` с полем `group: str` (`'wants'|'savings'`), без `category_group`/`linked_category_id`.
  - `DepositContribution(id, amount: Decimal, date, source: str)`.
  - `IncomeAllocation.to_deposit: bool` (default `False`).
  - `Goal`, `GoalContribution` больше не существуют.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_redesign.py`:

```python
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_model_shape(db):
    import app.models as m

    # Goal is gone
    assert not hasattr(m, "Goal")
    assert not hasattr(m, "GoalContribution")

    # SinkingFund uses `group`, not `category_group`
    fund = m.SinkingFund(name="Отпуск", target_amount=Decimal("50000"), group="savings")
    db.add(fund)
    db.commit()
    assert fund.group == "savings"
    assert not hasattr(fund, "category_group")

    # DepositContribution exists
    c = m.DepositContribution(amount=Decimal("1000"), date=date.today(), source="manual")
    db.add(c)
    db.commit()
    assert c.id is not None

    # IncomeAllocation has to_deposit
    a = m.IncomeAllocation(income_tx_id=1, amount=Decimal("5"), allocation_level=4, to_deposit=True)
    assert a.to_deposit is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py::test_model_shape -v`
Expected: FAIL (`Goal` still present / `category_group` still present / `DepositContribution` undefined).

- [ ] **Step 3: Edit models**

In `backend/app/models/__init__.py`:

Replace the `SinkingFund` columns block (currently `category_group`, `linked_category_id`, `linked_category`) so the class reads:

```python
class SinkingFund(Base):
    __tablename__ = "sinking_funds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    current_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    monthly_contribution: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    group: Mapped[str] = mapped_column(String(20), default="savings")  # wants | savings
    is_rolling: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    contributions: Mapped[list["SinkingFundContribution"]] = relationship(
        back_populates="fund", cascade="all, delete-orphan"
    )
```

Delete the `Goal` and `GoalContribution` classes entirely (lines around 203–231).

Add `to_deposit` to `IncomeAllocation` (after `allocation_level`):

```python
    to_deposit: Mapped[bool] = mapped_column(Boolean, default=False)
```

Add a new model next to `DepositSnapshot`:

```python
class DepositContribution(Base):
    __tablename__ = "deposit_contributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | allocation
    income_tx_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
```

`income_tx_id` links a contribution made via income allocation back to its income, so re-allocating that income can cleanly reverse the contribution (see Task 3 `rollback_for_income`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py::test_model_shape -v`
Expected: PASS.

- [ ] **Step 5: Fix import fallout & run full suite**

`grep -rn "Goal\b\|GoalContribution\|category_group\|linked_category" backend/app` — every remaining reference is fixed in later tasks, but to keep imports loading now, in `app/serializers.py` and `app/services/dashboard.py` temporarily remove `Goal`/`GoalContribution` from imports (full rewrites come in Tasks 6 and 9). Run `cd backend && .venv/bin/pytest tests/test_redesign.py -v`. Expected: PASS. (`test_v2.py` will be red until Task 5 — that's expected; do not run it yet.)

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/__init__.py backend/tests/test_redesign.py
git commit -m "refactor(models): two-pots model — drop Goal, SinkingFund.group, DepositContribution, IncomeAllocation.to_deposit"
```

---

### Task 2: Seed & schema reset

**Files:**
- Modify: `backend/app/seed.py`
- Create: `backend/alembic/versions/<rev>_redesign_reset.py`
- Test: `backend/tests/test_redesign.py`

**Interfaces:**
- Consumes: new model from Task 1.
- Produces: `load_demo_data(db)` and `load_clean_start(db)` create no savings-categories and no goals; demo копилки carry `group` in `{'wants','savings'}`; setting `deposit_monthly_target` exists.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_redesign.py`:

```python
from app.seed import load_demo_data, ensure_settings
from app.models import Category, SinkingFund, Setting


def test_seed_no_savings_categories_no_goals(db):
    ensure_settings(db)
    load_demo_data(db)

    groups = {c.group for c in db.query(Category).all()}
    assert "savings" not in groups
    assert groups <= {"needs", "wants", "income"}

    funds = db.query(SinkingFund).all()
    assert funds, "demo should create копилки"
    assert all(f.group in ("wants", "savings") for f in funds)
    assert any(f.group == "savings" for f in funds)

    assert db.query(Setting).filter(Setting.key == "deposit_monthly_target").first() is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py::test_seed_no_savings_categories_no_goals -v`
Expected: FAIL (savings categories present / Goal import error / setting missing).

- [ ] **Step 3: Rewrite seed**

In `backend/app/seed.py`:

Change the import line to: `from app.models import AppUser, Category, Debt, Setting, SinkingFund` (remove `Goal`).

Replace `DEMO_CATEGORIES` (drop the three savings rows and the `allocation_level` column is now informational only — keep `needs`/`wants` only):

```python
# (name, group, sort_order, allocation_level)  level: 1=fixed obligation, 2=variable need, 4=want
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
]
```

Add to `DEFAULT_SETTINGS` (right after `"deposit_rate_schedule": "[]",`):

```python
    "deposit_monthly_target": "0",
```

Replace `DEMO_SINKING_FUNDS` (use `group`, drop `linked_category_name`/`category_group`):

```python
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
```

In `load_demo_data`, delete the entire Goal block (`pillow = ...`, `big = ...`, both `db.add(Goal(...))`). Replace the fund-creation loop with:

```python
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
```

Update the module docstring: replace "goals, funds" with "funds (копилки)".

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Create the alembic reset revision**

Generate the stub: `cd backend && .venv/bin/alembic revision -m "redesign reset"`. Open the created file in `backend/alembic/versions/` and set its body to drop & recreate the changed tables (data is disposable):

```python
def upgrade() -> None:
    op.drop_table("goal_contributions")
    op.drop_table("goals")
    op.add_column("income_allocations", sa.Column("to_deposit", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("sinking_funds", sa.Column("group", sa.String(length=20), nullable=False, server_default="savings"))
    op.add_column("sinking_funds", sa.Column("icon", sa.String(length=64), nullable=True))
    op.add_column("sinking_funds", sa.Column("color", sa.String(length=16), nullable=True))
    op.drop_column("sinking_funds", "category_group")
    op.drop_column("sinking_funds", "linked_category_id")
    op.create_table(
        "deposit_contributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("income_tx_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    raise NotImplementedError("redesign reset is one-way")
```

Ensure `import sqlalchemy as sa` and `from alembic import op` are present at the top.

- [ ] **Step 6: Commit**

```bash
git add backend/app/seed.py backend/alembic/versions/ backend/tests/test_redesign.py
git commit -m "feat(seed): needs/wants categories, демо-копилки с group, deposit_monthly_target; alembic reset"
```

---

### Task 3: DepositService (own file)

**Files:**
- Create: `backend/app/services/deposit.py`
- Modify: `backend/app/services/plan.py` (remove old `DepositService`, re-export shim)
- Test: `backend/tests/test_redesign.py`

**Interfaces:**
- Produces:
  - `DepositService.get_balance(db) -> Decimal`
  - `DepositService.get_monthly_target(db) -> Decimal`
  - `DepositService.contribute(db, amount: Decimal, on_date: date | None = None, source: str = "manual", note: str | None = None) -> Decimal` (returns new balance; appends `DepositContribution`; bumps `deposit_balance` setting)
  - `DepositService.get_settings(db) -> dict` (keeps existing keys + `monthly_target`)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_redesign.py`:

```python
from app.services.deposit import DepositService
from app.models import DepositContribution


def test_deposit_contribute_grows_balance(db):
    ensure_settings(db)
    start = DepositService.get_balance(db)
    new_balance = DepositService.contribute(db, Decimal("10000"), source="manual")
    assert new_balance == start + Decimal("10000")
    assert DepositService.get_balance(db) == start + Decimal("10000")
    assert db.query(DepositContribution).count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py::test_deposit_contribute_grows_balance -v`
Expected: FAIL (`app.services.deposit` does not exist).

- [ ] **Step 3: Implement the service**

Create `backend/app/services/deposit.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import DepositContribution
from app.services.settings_store import get_setting, set_setting


class DepositService:
    @staticmethod
    def get_balance(db: Session) -> Decimal:
        return Decimal(get_setting(db, "deposit_balance", "0") or "0")

    @staticmethod
    def get_monthly_target(db: Session) -> Decimal:
        return Decimal(get_setting(db, "deposit_monthly_target", "0") or "0")

    @staticmethod
    def get_settings(db: Session) -> dict:
        return {
            "balance": DepositService.get_balance(db),
            "rate": Decimal(get_setting(db, "deposit_rate", "0") or "0"),
            "cap_day": int(get_setting(db, "deposit_cap_day", "1") or "1"),
            "start_date": (
                date.fromisoformat(get_setting(db, "deposit_start_date", "") )
                if get_setting(db, "deposit_start_date", "") else None
            ),
            "monthly_target": DepositService.get_monthly_target(db),
        }

    @staticmethod
    def contribute(
        db: Session,
        amount: Decimal,
        on_date: date | None = None,
        source: str = "manual",
        note: str | None = None,
        income_tx_id: int | None = None,
    ) -> Decimal:
        if amount <= 0:
            raise ValueError("amount must be positive")
        db.add(DepositContribution(amount=amount, date=on_date or date.today(),
                                   source=source, note=note, income_tx_id=income_tx_id))
        new_balance = DepositService.get_balance(db) + amount
        set_setting(db, "deposit_balance", str(new_balance))
        db.commit()
        return new_balance

    @staticmethod
    def rollback_for_income(db: Session, income_tx_id: int) -> None:
        """Remove deposit contributions previously made from this income and lower the balance."""
        rows = (
            db.query(DepositContribution)
            .filter(DepositContribution.income_tx_id == income_tx_id)
            .all()
        )
        if not rows:
            return
        removed = sum((r.amount for r in rows), Decimal("0"))
        for r in rows:
            db.delete(r)
        new_balance = max(Decimal("0"), DepositService.get_balance(db) - removed)
        set_setting(db, "deposit_balance", str(new_balance))
        db.commit()
```

In `backend/app/services/plan.py`, remove the old `DepositService` class and add at the bottom a re-export so existing imports keep working:

```python
from app.services.deposit import DepositService  # noqa: E402,F401  (moved; kept for back-compat imports)
```

Keep `DepositService.forecast_detailed` working: move that method into the new `deposit.py` (copy it verbatim from `plan.py`). Verify `forecast_detailed` signature and body are preserved.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py::test_deposit_contribute_grows_balance tests/test_deposit_calc.py -v`
Expected: PASS (new test + existing deposit-calc tests still green).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/deposit.py backend/app/services/plan.py backend/tests/test_redesign.py
git commit -m "feat(deposit): DepositService.contribute grows balance + logs DepositContribution"
```

---

### Task 4: SinkingFundService — `group` rename

**Files:**
- Modify: `backend/app/services/sinking_funds.py`
- Test: `backend/tests/test_redesign.py`

**Interfaces:**
- Produces: `FundSummary.group: str`; `SinkingFundService.create(..., group="savings")` and `.update(..., group=...)`; `spend_from_fund` no longer references `linked_category_id` (uses passed `category_id` only).

- [ ] **Step 1: Write the failing test**

Append:

```python
from app.services.sinking_funds import SinkingFundService


def test_fund_create_and_spend_with_group(db):
    f = SinkingFundService.create(db, name="Отпуск", target_amount=Decimal("100000"),
                                  monthly_contribution=Decimal("8000"), group="wants")
    assert f.group == "wants"
    SinkingFundService.contribute(db, f.id, Decimal("8000"), date.today())
    tx = SinkingFundService.spend_from_fund(db, f.id, Decimal("3000"), date.today(),
                                            category_id=None, user_id=None, comment=None)
    db.refresh(f)
    assert f.current_amount == Decimal("5000")
    assert tx.is_sinking_fund_spend and tx.fund_id == f.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py::test_fund_create_and_spend_with_group -v`
Expected: FAIL (`create()` has `category_group`, not `group`; `FundSummary` has no `group`).

- [ ] **Step 3: Edit the service**

In `backend/app/services/sinking_funds.py`:
- `FundSummary`: replace field `linked_category_id: int | None` with `group: str`.
- `get_summaries`: set `group=fund.group` instead of `linked_category_id=...`.
- `contribute`: unchanged.
- `spend_from_fund`: change `category_id=category_id or fund.linked_category_id` to `category_id=category_id`.
- `create`: change parameter `category_group: str = "needs"` to `group: str = "savings"`; build `SinkingFund(..., group=group)` (drop `category_group`/`linked_category_id`).
- `update`: add `group: str | None = None` param; if provided, `fund.group = group`.
- `last_contribution_date`: unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py::test_fund_create_and_spend_with_group -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/sinking_funds.py backend/tests/test_redesign.py
git commit -m "refactor(funds): SinkingFund.group replaces category_group; spend uses passed category only"
```

---

### Task 5: Allocation rewrite — three 50/30/20 buckets

**Files:**
- Modify: `backend/app/services/allocation.py`
- Modify: `backend/tests/test_v2.py` (update obsolete level-3 assumptions)
- Test: `backend/tests/test_redesign.py`

**Interfaces:**
- Produces:
  - `get_allocation_buckets(db, year, month, income_amount) -> list[AllocationBucket]` where
    `AllocationBucket = dataclass(group: str, label: str, percent: int, target_amount: Decimal, items: list[AllocationItem])`
    and `AllocationItem = dataclass(id: int, name: str, kind: str, suggested_amount: Decimal, group: str)` with `kind in {"category","fund","deposit"}` (deposit item has fixed `id=0`, `name="Вклад"`).
  - `allocate_income(db, income_tx_id, allocations)` where `AllocationInput = dataclass(category_id, fund_id, to_deposit: bool, amount, group: str)`; a `to_deposit` input calls `DepositService.contribute(..., source="allocation")`.
  - Helpers kept: `get_allocated_amount`, `get_unallocated_for_tx`, `get_unallocated_total`, `is_month_fully_allocated`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_redesign.py`:

```python
from app.models import Transaction, MonthlyPlan
from app.services.allocation import (
    get_allocation_buckets, allocate_income, AllocationInput, get_unallocated_for_tx,
)


def test_buckets_mirror_503020(db):
    ensure_settings(db); load_demo_data(db)
    y, mth = date.today().year, date.today().month
    buckets = get_allocation_buckets(db, y, mth, Decimal("100000"))
    groups = {b.group for b in buckets}
    assert groups == {"needs", "wants", "savings"}
    by = {b.group: b for b in buckets}
    assert by["needs"].percent == 50 and by["needs"].target_amount == Decimal("50000")
    assert by["wants"].percent == 30
    assert by["savings"].percent == 20
    # savings bucket includes the Вклад destination
    assert any(i.kind == "deposit" for i in by["savings"].items)


def test_allocate_to_deposit_grows_deposit(db):
    ensure_settings(db); load_demo_data(db)
    from app.services.deposit import DepositService
    tx = Transaction(type="income", amount=Decimal("20000"), date=date.today())
    db.add(tx); db.commit()
    before = DepositService.get_balance(db)
    allocate_income(db, tx.id, [AllocationInput(to_deposit=True, amount=Decimal("20000"), group="savings")])
    db.refresh(tx)
    assert tx.is_fully_allocated
    assert DepositService.get_balance(db) == before + Decimal("20000")
    assert get_unallocated_for_tx(db, tx) == Decimal("0")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py::test_buckets_mirror_503020 tests/test_redesign.py::test_allocate_to_deposit_grows_deposit -v`
Expected: FAIL (`get_allocation_buckets` undefined; `AllocationInput` has no `to_deposit`).

- [ ] **Step 3: Rewrite allocation.py**

Replace the `AllocationItem`/`AllocationLevel`/`LEVEL_LABELS`/`get_allocation_levels` machinery with the bucket model. Keep `get_allocated_amount`, `get_unallocated_for_tx`, `get_unallocated_total`, `is_month_fully_allocated`, `_limit_for_category` as-is. New code:

```python
from app.services.deposit import DepositService

BUCKETS = [("needs", "Нужды", 50), ("wants", "Желания", 30), ("savings", "Сбережения", 20)]


@dataclass
class AllocationItem:
    id: int
    name: str
    kind: str  # category | fund | deposit
    suggested_amount: Decimal
    group: str


@dataclass
class AllocationBucket:
    group: str
    label: str
    percent: int
    target_amount: Decimal
    items: list[AllocationItem] = field(default_factory=list)


def get_allocation_buckets(
    db: Session, year: int, month: int, income_amount: Decimal
) -> list[AllocationBucket]:
    plan = (
        db.query(MonthlyPlan)
        .options(joinedload(MonthlyPlan.limits))
        .filter(MonthlyPlan.year == year, MonthlyPlan.month == month)
        .first()
    )
    out: list[AllocationBucket] = []
    for group, label, percent in BUCKETS:
        target = (income_amount * Decimal(percent) / Decimal("100")).quantize(Decimal("0.01"))
        bucket = AllocationBucket(group=group, label=label, percent=percent, target_amount=target)

        if group in ("needs", "wants"):
            cats = (
                db.query(Category)
                .filter(Category.is_hidden.is_(False), Category.group == group)
                .order_by(Category.sort_order)
                .all()
            )
            for cat in cats:
                bucket.items.append(
                    AllocationItem(id=cat.id, name=cat.name, kind="category",
                                   suggested_amount=_limit_for_category(db, plan, cat), group=group)
                )

        funds = (
            db.query(SinkingFund)
            .filter(SinkingFund.is_active.is_(True), SinkingFund.group == group)
            .order_by(SinkingFund.id)
            .all()
        )
        for f in funds:
            bucket.items.append(
                AllocationItem(id=f.id, name=f.name, kind="fund",
                               suggested_amount=f.monthly_contribution, group=group)
            )

        if group == "savings":
            bucket.items.append(
                AllocationItem(id=0, name="Вклад", kind="deposit",
                               suggested_amount=DepositService.get_monthly_target(db), group="savings")
            )
        out.append(bucket)
    return out


@dataclass
class AllocationInput:
    category_id: int | None = None
    fund_id: int | None = None
    to_deposit: bool = False
    amount: Decimal = Decimal("0")
    group: str = "needs"
```

Rewrite `allocate_income` to clear old allocations (reverse fund and deposit contributions), then apply new ones:

```python
def allocate_income(db: Session, income_tx_id: int, allocations: list[AllocationInput]) -> Transaction:
    tx = db.query(Transaction).filter(Transaction.id == income_tx_id).first()
    if not tx or tx.type != "income":
        raise ValueError("Invalid income transaction")

    old = db.query(IncomeAllocation).filter(IncomeAllocation.income_tx_id == income_tx_id).all()
    for o in old:
        if o.fund_id:
            f = db.query(SinkingFund).filter(SinkingFund.id == o.fund_id).first()
            if f:
                f.current_amount = max(Decimal("0"), f.current_amount - o.amount)
    # reverse any prior deposit contributions made from this income (handles re-allocation)
    DepositService.rollback_for_income(db, income_tx_id)
    db.query(IncomeAllocation).filter(IncomeAllocation.income_tx_id == income_tx_id).delete()

    total = Decimal("0")
    for a in allocations:
        if a.amount <= 0:
            continue
        db.add(IncomeAllocation(
            income_tx_id=income_tx_id, category_id=a.category_id, fund_id=a.fund_id,
            to_deposit=a.to_deposit, amount=a.amount, allocated_at=datetime.utcnow(),
            allocation_level=0,
        ))
        total += a.amount
        if a.fund_id:
            f = db.query(SinkingFund).filter(SinkingFund.id == a.fund_id).first()
            if f:
                f.current_amount += a.amount
        if a.to_deposit:
            DepositService.contribute(db, a.amount, source="allocation", income_tx_id=income_tx_id)

    tx.is_fully_allocated = abs(total - tx.amount) <= Decimal("0.01")
    db.commit()
    db.refresh(tx)
    return tx
```

Note: `DepositService.contribute` commits internally; that is acceptable here (single request). Remove the now-unused `allocation_level` argument usage and `GROUP_PERCENTS` 50/30/20 remainder logic.

- [ ] **Step 4: Update test_v2.py**

`test_v2.py::test_unallocated_zero_after_allocate` uses `get_allocation_levels`/`item.allocation_level`. Replace its body to use buckets:

```python
def test_unallocated_zero_after_allocate(db):
    tx = Transaction(type="income", amount=Decimal("100000"), date=date.today())
    db.add(tx)
    db.commit()

    from app.services.allocation import get_allocation_buckets
    buckets = get_allocation_buckets(db, date.today().year, date.today().month, tx.amount)
    allocations = []
    assigned = Decimal("0")
    for b in buckets:
        for item in b.items:
            if item.suggested_amount > 0:
                allocations.append(AllocationInput(
                    category_id=item.id if item.kind == "category" else None,
                    fund_id=item.id if item.kind == "fund" else None,
                    to_deposit=item.kind == "deposit",
                    amount=item.suggested_amount, group=item.group))
                assigned += item.suggested_amount
    # top up remainder to the deposit so the income is fully allocated
    remainder = tx.amount - assigned
    if remainder > 0:
        allocations.append(AllocationInput(to_deposit=True, amount=remainder, group="savings"))
    allocate_income(db, tx.id, allocations)
    db.refresh(tx)
    assert tx.is_fully_allocated
```

Update the imports at the top of `test_v2.py`: replace `get_allocation_levels` with `get_allocation_buckets` and `AllocationInput`. Remove `get_unallocated_total` if its other use breaks (keep if still used).

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py tests/test_v2.py -v`
Expected: PASS (allocation tests green; any remaining `test_v2.py` failures must reference Goal/dashboard — those are fixed in Tasks 6/9; if a test imports `Goal`, mark it for update in Task 6).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/allocation.py backend/tests/test_v2.py backend/tests/test_redesign.py
git commit -m "feat(allocation): 50/30/20 buckets + Вклад destination; allocate_income grows deposit"
```

---

### Task 6: Dashboard — savings bucket from deposit + savings-funds

**Files:**
- Modify: `backend/app/services/dashboard.py`
- Test: `backend/tests/test_redesign.py`

**Interfaces:**
- Produces: `MonthSummary.groups` contains exactly needs/wants/savings; the savings group's `spent` = (deposit contributions this month) + (savings-fund contributions this month), `limit` = 20% of income_plan (or income_fact if no plan). `MonthSummary` no longer has `goals`. Keeps `funds`, `debts`.

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_dashboard_savings_counts_deposit(db):
    ensure_settings(db); load_demo_data(db)
    from app.services.deposit import DepositService
    from app.services.dashboard import DashboardService
    y, mth = date.today().year, date.today().month
    db.add(Transaction(type="income", amount=Decimal("100000"), date=date.today())); db.commit()
    DepositService.contribute(db, Decimal("15000"), source="manual")

    s = DashboardService.get_month_summary(db, y, mth)
    sav = next(g for g in s.groups if g.name == "savings")
    assert sav.spent >= Decimal("15000")
    assert {g.name for g in s.groups} == {"needs", "wants", "savings"}
    assert not hasattr(s, "goals") or s.goals == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py::test_dashboard_savings_counts_deposit -v`
Expected: FAIL (savings group still expense-based / `Goal` import error).

- [ ] **Step 3: Edit dashboard.py**

- Remove `Goal` from imports; delete `GoalSummary` usage and the `goals=` population (drop the `GoalSummary` dataclass and the query that builds goals). Leave `funds=SinkingFundService.get_summaries(db)`.
- Replace `DepositService` import to `from app.services.deposit import DepositService`.
- In the group-summary builder, special-case savings: compute `spent` as deposit + savings-fund contributions for the month rather than expense sum. Add helper near the top:

```python
def _savings_set_aside(db: Session, year: int, month: int) -> Decimal:
    from app.models import DepositContribution, SinkingFund, SinkingFundContribution
    dep = (
        db.query(func.coalesce(func.sum(DepositContribution.amount), 0))
        .filter(extract("year", DepositContribution.date) == year,
                extract("month", DepositContribution.date) == month)
        .scalar()
    ) or Decimal("0")
    fund = (
        db.query(func.coalesce(func.sum(SinkingFundContribution.amount), 0))
        .join(SinkingFund, SinkingFund.id == SinkingFundContribution.fund_id)
        .filter(SinkingFund.group == "savings",
                extract("year", SinkingFundContribution.date) == year,
                extract("month", SinkingFundContribution.date) == month)
        .scalar()
    ) or Decimal("0")
    return Decimal(dep) + Decimal(fund)
```

In the loop over `GROUP_LABELS` (needs/wants/savings), when `group == "savings"` set `spent = _savings_set_aside(db, year, month)` and `limit = (income_base * 20 / 100)` where `income_base = income_plan or income_fact`; for needs/wants keep the existing expense-sum + plan-limit logic. Ensure the savings group still appears even with no savings categories.

- Remove `goals` from `MonthSummary` (delete the field and the `GoalSummary` dataclass). Run `grep -n "goals\|GoalSummary" backend/app/services/dashboard.py` to confirm none remain.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py::test_dashboard_savings_counts_deposit -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/dashboard.py backend/tests/test_redesign.py
git commit -m "feat(dashboard): savings group = deposit + savings-fund contributions; drop goals"
```

---

### Task 7: Analytics — fact 50/30/20 block

**Files:**
- Modify: `backend/app/services/analytics.py`, `backend/app/api/analytics.py`
- Test: `backend/tests/test_redesign.py`

The analytics response is assembled inline in `api/analytics.py` (`@router.get("")`), calling `AnalyticsService.*` static methods. We add `AnalyticsService.split_503020(db, year, month)` and one extra key in the endpoint dict.

**Interfaces:**
- Produces: `AnalyticsService.split_503020(db, year, month) -> dict` = `{"needs": {"fact": float, "ideal": float, "percent": float}, "wants": {...}, "savings": {...}}` where `fact` is ₽ this month (needs/wants = expense sums by category group; savings = `_savings_set_aside` from Task 6), `ideal` = group% of month income, `percent` = fact share of total outflow. The `/api/analytics` response gains key `"split_503020"`.

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_analytics_has_503020_split(db):
    ensure_settings(db); load_demo_data(db)
    from app.services.analytics import AnalyticsService
    y, mth = date.today().year, date.today().month
    data = AnalyticsService.split_503020(db, y, mth)
    assert set(data.keys()) == {"needs", "wants", "savings"}
    assert set(data["needs"].keys()) == {"fact", "ideal", "percent"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py::test_analytics_has_503020_split -v`
Expected: FAIL (`split_503020` undefined).

- [ ] **Step 3: Implement**

In `backend/app/services/analytics.py`, add a static method to `AnalyticsService`:

```python
    @staticmethod
    def split_503020(db: Session, year: int, month: int) -> dict:
        from decimal import Decimal
        from sqlalchemy import extract, func
        from app.models import Category, Transaction
        from app.services.dashboard import _savings_set_aside

        def expense_for(group: str) -> Decimal:
            return Decimal(str((
                db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .join(Category, Category.id == Transaction.category_id)
                .filter(Transaction.type == "expense", Category.group == group,
                        extract("year", Transaction.date) == year,
                        extract("month", Transaction.date) == month)
                .scalar()
            ) or "0"))

        income = Decimal(str((
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(Transaction.type == "income",
                    extract("year", Transaction.date) == year,
                    extract("month", Transaction.date) == month)
            .scalar()
        ) or "0"))

        needs, wants = expense_for("needs"), expense_for("wants")
        savings = _savings_set_aside(db, year, month)
        total = (needs + wants + savings) or Decimal("1")
        out = {}
        for name, fact, pct in (("needs", needs, 50), ("wants", wants, 30), ("savings", savings, 20)):
            out[name] = {
                "fact": float(fact),
                "ideal": float(income * Decimal(pct) / Decimal("100")),
                "percent": float(fact / total * 100),
            }
        return out
```

In `backend/app/api/analytics.py`, add to the dict returned by `@router.get("")`:

```python
        "split_503020": AnalyticsService.split_503020(db, year, month),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py::test_analytics_has_503020_split -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/analytics.py backend/app/api/analytics.py backend/tests/test_redesign.py
git commit -m "feat(analytics): split_503020 fact-vs-ideal block"
```

---

### Task 8: Plan — 50/30/20 meter + «подогнать»

**Files:**
- Modify: `backend/app/services/plan.py`, `backend/app/api/plan.py`
- Test: `backend/tests/test_redesign.py`

**Interfaces:**
- Produces:
  - `PlanService.meter_503020(db, year, month) -> dict`: `{"needs": {"allocated": float, "target": float}, "wants": {...}, "savings": {...}}` where `allocated` = sum of category limits in that group (+ savings-fund monthly_contribution + deposit monthly_target for savings), `target` = group% of `expected_income`.
  - `PlanService.fit_503020(db, year, month) -> MonthlyPlan`: scales existing category limits within needs/wants groups proportionally so each group total equals its target; if a group has no limits, splits target equally across that group's non-hidden categories.

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_plan_meter_and_fit(db):
    ensure_settings(db); load_demo_data(db)
    from app.services.plan import PlanService
    y, mth = date.today().year, date.today().month
    plan = PlanService.get_or_create_plan(db, y, mth)
    plan.expected_income = Decimal("100000"); db.commit()

    PlanService.fit_503020(db, y, mth)
    meter = PlanService.meter_503020(db, y, mth)
    assert abs(meter["needs"]["target"] - 50000) < 1
    assert abs(meter["needs"]["allocated"] - 50000) < 1  # fit made needs limits sum to target
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py::test_plan_meter_and_fit -v`
Expected: FAIL (`meter_503020`/`fit_503020` undefined).

- [ ] **Step 3: Implement**

In `backend/app/services/plan.py`, add to `PlanService`:

```python
    @staticmethod
    def meter_503020(db: Session, year: int, month: int) -> dict:
        from app.models import Category, CategoryLimit
        from app.services.deposit import DepositService
        plan = PlanService.get_or_create_plan(db, year, month)
        income = plan.expected_income or Decimal("0")
        out = {}
        for group, pct in (("needs", 50), ("wants", 30), ("savings", 20)):
            target = income * Decimal(pct) / Decimal("100")
            if group in ("needs", "wants"):
                allocated = (
                    db.query(func.coalesce(func.sum(CategoryLimit.limit_amount), 0))
                    .join(Category, Category.id == CategoryLimit.category_id)
                    .filter(CategoryLimit.plan_id == plan.id, Category.group == group)
                    .scalar()
                ) or Decimal("0")
            else:
                from app.models import SinkingFund
                fund_sum = (
                    db.query(func.coalesce(func.sum(SinkingFund.monthly_contribution), 0))
                    .filter(SinkingFund.is_active.is_(True), SinkingFund.group == "savings")
                    .scalar()
                ) or Decimal("0")
                allocated = Decimal(fund_sum) + DepositService.get_monthly_target(db)
            out[group] = {"allocated": float(allocated), "target": float(target)}
        return out

    @staticmethod
    def fit_503020(db: Session, year: int, month: int) -> MonthlyPlan:
        from app.models import Category, CategoryLimit
        plan = PlanService.get_or_create_plan(db, year, month)
        income = plan.expected_income or Decimal("0")
        for group, pct in (("needs", 50), ("wants", 30)):
            target = income * Decimal(pct) / Decimal("100")
            cats = db.query(Category).filter(Category.is_hidden.is_(False), Category.group == group).all()
            limits = {l.category_id: l for l in plan.limits if l.category_id in {c.id for c in cats}}
            current_total = sum((l.limit_amount for l in limits.values()), Decimal("0"))
            if current_total > 0:
                factor = target / current_total
                for l in limits.values():
                    l.limit_amount = (l.limit_amount * factor).quantize(Decimal("0.01"))
            elif cats:
                per = (target / len(cats)).quantize(Decimal("0.01"))
                for c in cats:
                    existing = limits.get(c.id)
                    if existing:
                        existing.limit_amount = per
                    else:
                        db.add(CategoryLimit(plan_id=plan.id, category_id=c.id, limit_amount=per))
        db.commit()
        db.refresh(plan)
        return plan
```

In `backend/app/api/plan.py`: confirm the existing `savePlan`/auto-distribute endpoint, and (a) add `GET /api/plan/{year}/{month}/meter` returning `PlanService.meter_503020(db, year, month)`; (b) change the auto-distribute path so `auto_distribute=True` calls `PlanService.fit_503020` instead of equal-split. (Read the file first to wire into existing route names.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py::test_plan_meter_and_fit -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/plan.py backend/app/api/plan.py backend/tests/test_redesign.py
git commit -m "feat(plan): 50/30/20 meter + proportional fit_503020"
```

---

### Task 9: Serializers + API wiring + remove goals router

**Files:**
- Modify: `backend/app/serializers.py`, `backend/app/api/funds.py`, `backend/app/api/deposit.py`, `backend/app/api/allocation.py`, `backend/app/main.py`
- Delete: `backend/app/api/goals.py`, `backend/app/services/goals.py`
- Test: `backend/tests/test_redesign.py`

**Interfaces:**
- Produces:
  - `fund_dict(f)` returns `group` (not `category_group`/`linked_category_id`).
  - `deposit_dict(db)` → `{balance, rate, cap_day, start_date, monthly_target}` (floats / iso).
  - `POST /api/deposit/contribute {amount, date?, note?}` → updated deposit dict.
  - `GET /api/allocation/{tx_id}` returns `buckets` (not `levels`); `POST /api/allocation/{tx_id}` accepts items with `to_deposit` and `group`.
  - `/api/goals*` removed.

- [ ] **Step 1: Write the failing test (API via TestClient)**

Append:

```python
def test_api_contract(db, monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main
    # point the app's DB dependency at our in-memory session
    main.app.dependency_overrides = {}
    from app.db import get_db
    ensure_settings(db); load_demo_data(db)
    main.app.dependency_overrides[get_db] = lambda: db
    client = TestClient(main.app)

    assert client.get("/api/goals").status_code in (404, 405)

    f = client.get("/api/funds").json()[0]
    assert "group" in f and "category_group" not in f

    dep = client.post("/api/deposit/contribute", json={"amount": 5000}).json()
    assert dep["balance"] >= 5000

    tx = client.post("/api/transactions", json={"type": "income", "amount": 30000,
                                                "date": str(date.today())}).json()
    view = client.get(f"/api/allocation/{tx['id']}").json()
    assert "buckets" in view
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_redesign.py::test_api_contract -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

- `serializers.py`: in `fund_dict` replace `category_group`/`linked_category_id` with `"group": f.group`; delete `goal_dict` and `goal_contribution_dict`; remove `Goal`/`GoalContribution` from imports; add:

```python
def deposit_dict(s: dict) -> dict:
    return {
        "balance": float(s["balance"]),
        "rate": float(s["rate"]),
        "cap_day": s["cap_day"],
        "start_date": s["start_date"].isoformat() if s["start_date"] else None,
        "monthly_target": float(s["monthly_target"]),
    }
```

- `api/funds.py`: `FundBody` — replace `category_group: str = "needs"` with `group: str = "savings"`; remove `linked_category_id`. Pass `group=body.group` to `create`/`update`.
- `api/deposit.py`: add route:

```python
class ContributeBody(BaseModel):
    amount: Decimal
    date: date | None = None
    note: str | None = None

@router.post("/contribute")
def contribute(body: ContributeBody, db: Session = Depends(get_db)):
    from app.services.deposit import DepositService
    DepositService.contribute(db, body.amount, body.date, "manual", body.note)
    return _settings_response(db)
```
Update `_settings_response` to include `monthly_target` and accept setting it in `update_deposit` (`deposit_monthly_target`).
- `api/allocation.py`: rename `get_allocation_levels`→`get_allocation_buckets`; return `"buckets": buckets` instead of `"levels"`; `AllocItem` gains `to_deposit: bool = False` and `group: str = "needs"`, drop `allocation_level`; build `AllocationInput(..., to_deposit=i.to_deposit, group=i.group)`. `existing` items add `"to_deposit": a.to_deposit`.
- `main.py`: remove `from app.api import goals` and its `app.include_router(goals.router)`.
- Delete `backend/app/api/goals.py` and `backend/app/services/goals.py` (verify nothing else imports them: `grep -rn "services.goals\|api import goals\|api.goals" backend/app`). Dashboard's earlier `months_to_goal` use is already gone (Task 6).

- [ ] **Step 4: Run test to verify it passes + full suite**

Run: `cd backend && .venv/bin/pytest -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add -A backend
git commit -m "feat(api): fund.group, deposit/contribute, allocation buckets; remove goals router"
```

---

# PHASE 2 — Frontend (build + preview verify)

> No frontend unit-test runner exists. Each task: edit → `make dev-api` + `make dev-web` (or preview tools) → verify in browser → commit. Start servers once at the top of Phase 2 with the preview tooling and reuse.

### Task 10: api.ts contract sync

**Files:**
- Modify: `frontend/src/lib/api.ts`

**Interfaces:**
- Produces: TS types `FundSummary` (with `group: 'wants'|'savings'`, no `category_group`/`linked_category_id`), `AllocationBucket`/`AllocationView` (`buckets`, items have `kind: 'category'|'fund'|'deposit'`, `group`), `Deposit` type with `monthly_target`. Methods: remove `goals/createGoal/updateGoal/deleteGoal/goalContribute`; add `depositContribute`, `planMeter`; `allocate` items carry `to_deposit`,`group`.

- [ ] **Step 1: Edit types & methods**

In `frontend/src/lib/api.ts`:
- `FundSummary`: replace `category_group`/`linked_category_id` with `group: 'wants' | 'savings'`.
- Delete `GoalSummary` interface and `goals` from `MonthSummary` (replace dashboard usage in Task 16).
- Replace `AllocationItem`/`AllocationLevel`/`AllocationView` with:

```ts
export interface AllocationItem {
  id: number
  name: string
  kind: 'category' | 'fund' | 'deposit'
  suggested_amount: number
  group: 'needs' | 'wants' | 'savings'
}
export interface AllocationBucket {
  group: 'needs' | 'wants' | 'savings'
  label: string
  percent: number
  target_amount: number
  items: AllocationItem[]
}
export interface AllocationView {
  transaction: { id: number; amount: number; date: string; is_fully_allocated: boolean }
  unallocated: number
  buckets: AllocationBucket[]
  existing: { category_id: number | null; fund_id: number | null; to_deposit: boolean; amount: number }[]
}
export interface Deposit {
  balance: number; rate: number; cap_day: number; start_date: string | null; monthly_target: number
}
```

- Remove the four `goal*` methods. Add:

```ts
  depositContribute: (b: { amount: number; date?: string; note?: string }) =>
    req<Deposit>('POST', '/deposit/contribute', b),
  planMeter: (y: number, m: number) =>
    req<Record<string, { allocated: number; target: number }>>('GET', `/plan/${y}/${m}/meter`),
```

- `deposit()`/`updateDeposit()` return `Deposit`.

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: errors ONLY in `.svelte` consumers you will fix in Tasks 11–17 (e.g. `More.svelte` goals usage). The `api.ts` file itself must be clean. If `tsc` flags `api.ts` lines, fix them.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(api.ts): buckets, fund.group, deposit contribute/monthly_target; drop goals"
```

---

### Task 11: AllocationSheet — three 50/30/20 buckets

**Files:**
- Modify: `frontend/src/lib/components/AllocationSheet.svelte`

**Interfaces:**
- Consumes: `api.allocationView` (`buckets`), `api.allocate` (items `{category_id, fund_id, to_deposit, amount, group}`).

- [ ] **Step 1: Rewrite the component**

Replace levels logic with buckets. Key changes (keep existing styles, adapt class names):
- `key` becomes `${group}:${kind}:${id}`.
- Iterate `view.buckets`; each bucket renders a header with `bucket.label` + percent + a per-bucket counter `распределено / target_amount`.
- `autoFill()` sets each item to `Math.round(item.suggested_amount)`.
- `save()` builds allocations from `view.buckets`:

```ts
for (const b of view.buckets) {
  for (const it of b.items) {
    const amt = amounts[keyOf(b.group, it.kind, it.id)] || 0
    if (amt <= 0) continue
    allocations.push({
      category_id: it.kind === 'category' ? it.id : null,
      fund_id: it.kind === 'fund' ? it.id : null,
      to_deposit: it.kind === 'deposit',
      amount: amt,
      group: b.group,
    })
  }
}
```
- Prefill from `view.existing`: deposit key when `to_deposit`, fund key when `fund_id`, else category key.
- Per-bucket counter colour: green when `bucketAssigned >= target_amount`.

- [ ] **Step 2: Verify in preview**

Add income via FAB → allocation sheet opens. Confirm three sections (Нужды/Желания/Сбережения) with percents, that «Вклад» appears under Сбережения, autofill fills numbers, save closes and dashboard updates. Check `preview_console_logs` for errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/components/AllocationSheet.svelte
git commit -m "feat(allocation-ui): mirror 50/30/20 buckets with Вклад destination"
```

---

### Task 12: TxForm — grouped categories + remaining-in-bucket

**Files:**
- Modify: `frontend/src/lib/components/TxForm.svelte`
- Consumes: `api.dashboard(year, month)` groups for remaining-in-bucket; `period` store.

- [ ] **Step 1: Edit**

For expense type, render category chips grouped under `Нужды` / `Желания` headers (filter `c.group === 'needs'` then `'wants'`; income unchanged). When a category is selected, fetch/derive the current month dashboard group for that category's group and show a thin bar: `осталось в [label]: money(limit - spent) из money(limit)`. Load dashboard once via `api.dashboard($period.year, $period.month)`; map `group` → `{spent, limit}`.

- [ ] **Step 2: Verify in preview**

Open add-expense sheet: categories grouped under headers; pick one → remaining line shows. No console errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/components/TxForm.svelte
git commit -m "feat(txform): group categories by 50/30/20 + remaining-in-bucket hint"
```

---

### Task 13: Plan — 50/30/20 meter + «Подогнать»

**Files:**
- Modify: `frontend/src/routes/Plan.svelte`
- Consumes: `api.planMeter(y, m)`; existing `api.savePlan({auto_distribute:true})` now triggers `fit_503020`.

- [ ] **Step 1: Edit**

At the top of the plan page add a live meter: three rows (Нужды/Желания/Сбережения) each a `ProgressBar` of `allocated` vs `target` from `api.planMeter`. Recompute `allocated` locally as the user edits `limits` (sum per group) so the meter is live; `target` from `expected_income * pct`. Rename the button to «Подогнать под 50/30/20» (handler still calls `recalc()` → `savePlan({auto_distribute:true})`). Refetch meter after save.

- [ ] **Step 2: Verify in preview**

Plan screen shows three-bar meter; editing a limit moves the bar; «Подогнать» scales limits to hit targets.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/Plan.svelte
git commit -m "feat(plan-ui): live 50/30/20 meter + Подогнать"
```

---

### Task 14: Deposit — пополнить, grow-only, журнал

**Files:**
- Modify: `frontend/src/routes/Deposit.svelte`
- Consumes: `api.deposit()` (`monthly_target`), `api.depositContribute`, `api.updateDeposit`.

- [ ] **Step 1: Edit**

- Make the balance field read-only (display), replace «Сохранить баланс» with a «Пополнить вклад» input + button calling `api.depositContribute({amount})`, then refetch and toast «Вклад пополнен».
- Add an editable «Цель пополнения в месяц» bound to `dep.monthly_target`, saved via `api.updateDeposit({ monthly_target })`.
- Keep rate field + calculator. Remove any «снять/withdraw» affordance (none currently — just ensure balance isn't directly editable).

- [ ] **Step 2: Verify in preview**

Deposit screen: пополнить increases balance; monthly target persists; calculator still computes.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/Deposit.svelte
git commit -m "feat(deposit-ui): grow-only balance, пополнить, monthly target"
```

---

### Task 15: Analytics — fact 50/30/20 block

**Files:**
- Modify: `frontend/src/routes/Analytics.svelte`
- Consumes: `data.split_503020`.

- [ ] **Step 1: Edit**

Add a block «Факт 50/30/20» above «Топ категорий»: three rows, each showing `fact` ₽, `percent`%, and target `ideal` ₽; colour the percent green/red vs the bucket's nominal (50/30/20). Use existing `.pbar` style with width = `percent`.

- [ ] **Step 2: Verify in preview**

Analytics shows the new block with three buckets and no console errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/Analytics.svelte
git commit -m "feat(analytics-ui): факт 50/30/20 block"
```

---

### Task 16: Dashboard — target % labels, drop goals

**Files:**
- Modify: `frontend/src/routes/Dashboard.svelte`
- Consumes: `summary.groups` (now includes savings fed by deposit/funds).

- [ ] **Step 1: Edit**

In the 50/30/20 card, append the nominal target to each group label (e.g. «Сбережения 20%») and show `money(spent)` as «отложено» wording for the savings group. Remove any reference to `summary.goals` (none rendered today, but verify). No other behavioural change.

- [ ] **Step 2: Verify in preview**

Dashboard renders three group bars; savings bar reflects deposit contributions made on the Deposit screen.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/Dashboard.svelte
git commit -m "feat(dashboard-ui): 50/30/20 target labels; savings = set-aside"
```

---

### Task 17: More — копилки with target, remove Goals section

**Files:**
- Modify: `frontend/src/routes/More.svelte`
- Consumes: `api.funds` (with `group`, `target_amount`), `api.fundContribute`, `api.fundSpend`.

- [ ] **Step 1: Edit**

- Delete the entire «Цели» section and all `goal*` handlers (`contributeGoal`, `saveGoalEdit`, `delGoal`, `createGoal`).
- Копилки section: in create/edit forms add a `group` selector (`Желания`/`Сбережения`) and keep `target_amount`, `monthly_contribution`, `target_date`, `is_rolling`. Add a «Потратить» button alongside «Пополнить» calling `api.fundSpend(id, { amount })`.
- `reload()`: drop `api.goals()`.

- [ ] **Step 2: Verify in preview**

«Ещё» shows Копилки (with group + target + потратить) and Долги only; no Цели; create/edit/contribute/spend all work.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/More.svelte
git commit -m "feat(more-ui): merge Goals into Копилки (group + target + spend)"
```

---

# PHASE 3 — FAQ + onboarding

### Task 18: FAQ route, nav entry, onboarding link

**Files:**
- Create: `frontend/src/routes/Faq.svelte`
- Modify: `frontend/src/App.svelte`, `frontend/src/routes/More.svelte`, `frontend/src/lib/components/Onboarding.svelte`

**Interfaces:**
- Produces: hash route `#/faq` rendering `Faq.svelte`; entry link from More and Onboarding.

- [ ] **Step 1: Create Faq.svelte**

Static scenario cards (no backend). Each card: title, 2–4 steps, a small inline SVG/CSS diagram. Cover the 8 scenarios from the spec (как устроены деньги; доход и распределение; расход; копилки отложить/потратить; вклад; что такое 50/30/20; спланировать месяц; закрыть месяц). Use a `scenarios` array of `{title, icon, steps: string[]}` rendered as `.card`s, with one hero diagram at top showing the two pots (Вклад vs Копилки) and the 50/30/20 split. Match `app.css` tokens; mobile-first.

```svelte
<script lang="ts">
  const scenarios = [
    { icon: 'ti-wallet', title: 'Как устроены деньги',
      steps: ['Доход делится на 3 корзины: Нужды 50%, Желания 30%, Сбережения 20%.',
              'Сбережения уходят в два места: Вклад (заморожен, только растёт) и Копилки (можно тратить).'] },
    { icon: 'ti-arrow-down-circle', title: 'Записать доход и распределить',
      steps: ['Нажмите + → Доход → сумма.', 'Распределите по корзинам 50/30/20.',
              'Часть в Вклад, часть в копилки — остаток виден сверху.'] },
    { icon: 'ti-arrow-up-circle', title: 'Записать расход',
      steps: ['Нажмите + → Расход.', 'Категории сгруппированы по корзинам.',
              'Видно, сколько осталось в корзине за месяц.'] },
    { icon: 'ti-pig-money', title: 'Копилки: отложить и потратить',
      steps: ['Откройте «Ещё» → Копилки.', '«Пополнить» — отложить.', '«Потратить» — снять на мелкую цель.'] },
    { icon: 'ti-building-bank', title: 'Вклад: пополнить и следить за ростом',
      steps: ['Вкладку «Вклад».', '«Пополнить» — баланс растёт.', 'Снять нельзя; калькулятор показывает прогноз с %.'] },
    { icon: 'ti-percentage', title: 'Что такое 50/30/20',
      steps: ['50% — обязательные нужды, 30% — желания, 20% — в сбережения.',
              'Отклонение видно на Главной, в Плане и в Аналитике.'] },
    { icon: 'ti-calendar', title: 'Спланировать месяц',
      steps: ['Вкладка «План» → ожидаемый доход.', 'Задайте лимиты категорий.',
              '«Подогнать под 50/30/20» подровняет суммы под цель.'] },
    { icon: 'ti-lock', title: 'Закрыть месяц',
      steps: ['В «Плане» → «Закрыть месяц».', 'Остатки лимитов переносятся на следующий месяц.'] },
  ]
</script>

<div class="page-header"><h1>Как это работает</h1></div>
<div class="page">
  <div class="card hero">
    <div class="pots">
      <div class="pot"><i class="ti ti-building-bank"></i><strong>Вклад</strong><span class="muted">заморожен, +%</span></div>
      <div class="pot"><i class="ti ti-pig-money"></i><strong>Копилки</strong><span class="muted">можно тратить</span></div>
    </div>
    <div class="split">
      <span class="seg needs">Нужды 50%</span><span class="seg wants">Желания 30%</span><span class="seg sav">Сбереж. 20%</span>
    </div>
  </div>
  {#each scenarios as s}
    <div class="card faq">
      <div class="faq-h"><i class="ti {s.icon}"></i><strong>{s.title}</strong></div>
      <ol>{#each s.steps as st}<li>{st}</li>{/each}</ol>
    </div>
  {/each}
</div>

<style>
  .hero { display: flex; flex-direction: column; gap: var(--space-3); }
  .pots { display: flex; gap: var(--space-3); }
  .pot { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px; padding: var(--space-3);
         background: var(--bg-surface); border-radius: var(--radius-md); }
  .pot i { font-size: 26px; color: var(--gold); }
  .split { display: flex; border-radius: var(--radius-sm); overflow: hidden; font-size: var(--text-xs); }
  .seg { padding: 6px 0; text-align: center; color: #fff; }
  .seg.needs { background: var(--blue); flex: 50; }
  .seg.wants { background: var(--yellow); flex: 30; }
  .seg.sav { background: var(--green); flex: 20; }
  .faq-h { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
  .faq-h i { font-size: 20px; color: var(--blue); }
  .faq ol { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px; font-size: var(--text-sm); color: var(--text-secondary); }
</style>
```

- [ ] **Step 2: Wire the route**

In `frontend/src/App.svelte`: import `Faq` and add `{:else if $route === 'faq'}<Faq />`.
In `frontend/src/routes/More.svelte`: add a link row at the top: `<a class="btn btn-ghost" href="#/faq"><i class="ti ti-help"></i> Как это работает</a>`.
In `frontend/src/lib/components/Onboarding.svelte`: add under the options `<a class="muted faq-link" href="#/faq">Как это работает →</a>` (visible after a mode is picked is fine, or always).

- [ ] **Step 3: Verify in preview**

Navigate to `#/faq` (and via More): all 8 cards + hero diagram render, mobile width looks right (`preview_resize` 390px), no console errors. `preview_screenshot` for the record.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/routes/Faq.svelte frontend/src/App.svelte frontend/src/routes/More.svelte frontend/src/lib/components/Onboarding.svelte
git commit -m "feat(faq): in-app How-it-works section with scenario cards"
```

---

## Final verification

- [ ] `cd backend && .venv/bin/pytest -v` → all green.
- [ ] `cd frontend && npx tsc --noEmit` → clean.
- [ ] `cd frontend && npm run build` → builds.
- [ ] Manual flow in preview: onboarding (demo) → доход → распределение по 3 корзинам (часть в Вклад) → Главная (savings-бар вырос) → расход (категории сгруппированы) → Вклад пополнить → копилка отложить/потратить → План «Подогнать» → Аналитика (факт 50/30/20) → FAQ.
- [ ] Commit any final fixes.

---

## Self-Review notes (coverage of spec)

- Two pots / drop Goal / savings categories removed → Tasks 1, 2, 6.
- Deposit integration (grows on allocation + manual) → Tasks 3, 5, 14.
- Allocation mirrors 50/30/20 + Вклад destination → Tasks 5, 11.
- Auto-distribute rewrite (allocation autofill + plan fit) → Tasks 5, 8, 13.
- 50/30/20 everywhere (TxForm, Plan, Analytics, Dashboard) → Tasks 12, 13, 15, 16.
- FAQ → Task 18. Onboarding update → Tasks 2 (data), 18 (link).
- Contract sync TS↔Python → Tasks 9, 10.
