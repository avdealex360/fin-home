from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers models with Base.metadata before create_all
from app.db import Base


def _authenticate(client) -> None:
    """Inject a valid session cookie so TestClient calls pass the auth middleware."""
    from app.services.auth import SESSION_COOKIE, create_session_token

    client.cookies.set(SESSION_COOKIE, create_session_token())


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

    # IncomeAllocation no longer has to_deposit — deposit is a standalone calculator
    a = m.IncomeAllocation(income_tx_id=1, amount=Decimal("5"), allocation_level=4)
    assert not hasattr(a, "to_deposit")


from app.seed import load_demo_data, ensure_settings
from app.models import Category, SinkingFund, Setting


def test_seed_has_savings_category_no_goals(db):
    ensure_settings(db)
    load_demo_data(db)

    groups = {c.group for c in db.query(Category).all()}
    assert "savings" in groups, "a savings category must exist so limits/spend can be tracked like needs/wants"
    assert groups <= {"needs", "wants", "savings", "income"}

    funds = db.query(SinkingFund).all()
    assert funds, "demo should create копилки"
    assert all(f.group in ("wants", "savings") for f in funds)
    assert any(f.group == "savings" for f in funds)

    assert db.query(Setting).filter(Setting.key == "deposit_monthly_target").first() is not None


from app.models import Transaction, MonthlyPlan
from app.services.allocation import (
    get_allocation_buckets, allocate_income, AllocationInput, get_unallocated_for_tx,
)
from app.services.sinking_funds import SinkingFundService


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
    # savings bucket now offers its category (e.g. «Пополнение вклада») like needs/wants,
    # not a special "deposit" destination — deposit is a standalone calculator now.
    assert any(i.kind == "category" for i in by["savings"].items)
    assert not any(i.kind == "deposit" for i in by["savings"].items)


def test_allocate_to_savings_category(db):
    ensure_settings(db); load_demo_data(db)
    savings_cat = db.query(Category).filter(Category.group == "savings").first()
    assert savings_cat, "demo data must seed a savings category"
    tx = Transaction(type="income", amount=Decimal("20000"), date=date.today())
    db.add(tx); db.commit()
    allocate_income(db, tx.id, [AllocationInput(category_id=savings_cat.id, amount=Decimal("20000"), group="savings")])
    db.refresh(tx)
    assert tx.is_fully_allocated
    assert get_unallocated_for_tx(db, tx) == Decimal("0")


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


def test_dashboard_savings_counts_fund_contributions(db):
    """Savings.spent must count копилка contributions — the вклад calculator has
    no ledger at all anymore, so it structurally cannot move this number."""
    ensure_settings(db); load_demo_data(db)
    from app.services.dashboard import DashboardService
    from app.services.sinking_funds import SinkingFundService

    y, mth = date.today().year, date.today().month
    db.add(Transaction(type="income", amount=Decimal("100000"), date=date.today())); db.commit()

    fund = db.query(SinkingFund).filter(SinkingFund.group == "savings").first()
    assert fund, "demo data must include a savings копилка"
    SinkingFundService.contribute(db, fund.id, Decimal("5000"), date.today())

    s = DashboardService.get_month_summary(db, y, mth)
    sav = next(g for g in s.groups if g.name == "savings")
    assert sav.spent == Decimal("5000")
    assert {g.name for g in s.groups} == {"needs", "wants", "savings"}
    assert not hasattr(s, "goals") or s.goals == []


def test_savings_category_limit_shows_up_in_group_limit(db):
    """A CategoryLimit on a savings-group category must reach Dashboard's group.limit,
    exactly like needs/wants — this was the bug: savings limits were entered but ignored."""
    ensure_settings(db); load_demo_data(db)
    from app.services.dashboard import DashboardService
    from app.services.plan import PlanService

    y, mth = date.today().year, date.today().month
    cat = db.query(Category).filter(Category.group == "savings").first()
    assert cat, "demo data must seed a savings category"

    plan = PlanService.get_or_create_plan(db, y, mth)
    PlanService.save_plan(db, y, mth, Decimal("100000"), category_limits={cat.id: Decimal("20000")})

    s = DashboardService.get_month_summary(db, y, mth)
    sav = next(g for g in s.groups if g.name == "savings")
    assert sav.limit == Decimal("20000")

    meter = PlanService.meter_503020(db, y, mth)
    assert meter["savings"]["allocated"] == 20000.0


def test_analytics_has_503020_split(db):
    ensure_settings(db); load_demo_data(db)
    from app.services.analytics import AnalyticsService
    y, mth = date.today().year, date.today().month
    data = AnalyticsService.split_503020(db, y, mth)
    assert set(data.keys()) == {"needs", "wants", "savings"}
    assert set(data["needs"].keys()) == {"fact", "ideal", "percent"}


def test_plan_meter_needs_target(db):
    ensure_settings(db); load_demo_data(db)
    from app.services.plan import PlanService
    y, mth = date.today().year, date.today().month
    plan = PlanService.get_or_create_plan(db, y, mth)
    plan.expected_income = Decimal("100000"); db.commit()

    meter = PlanService.meter_503020(db, y, mth)
    assert abs(meter["needs"]["target"] - 50000) < 1


def test_api_contract(tmp_path):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.models  # noqa: F401
    import app.main as main
    from app.db import Base, get_db

    # Use a file-based SQLite so connections work across threads
    db_path = tmp_path / "test_api.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    # Seed data in one session
    seed_session = TestSession()
    ensure_settings(seed_session)
    load_demo_data(seed_session)
    seed_session.close()

    # Override get_db to produce sessions from our test engine
    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    # point the app's DB dependency at our test sessions
    main.app.dependency_overrides = {}
    main.app.dependency_overrides[get_db] = override_get_db

    client = TestClient(main.app)
    _authenticate(client)

    assert client.get("/api/goals").status_code in (404, 405)

    f = client.get("/api/funds").json()[0]
    assert "group" in f and "category_group" not in f

    dep = client.get("/api/deposit").json()
    assert "term_months" in dep and "balance" not in dep

    tx = client.post("/api/transactions", json={"type": "income", "amount": 30000,
                                                "date": str(date.today())}).json()
    view = client.get(f"/api/allocation/{tx['id']}").json()
    assert "buckets" in view

    savings_cat = next(
        item for b in view["buckets"] if b["group"] == "savings" for item in b["items"] if item["kind"] == "category"
    )
    alloc_resp = client.post(f"/api/allocation/{tx['id']}", json={
        "allocations": [{"category_id": savings_cat["id"], "amount": 30000, "group": "savings"}]
    })
    assert alloc_resp.status_code == 200, alloc_resp.text
    assert alloc_resp.json()["is_fully_allocated"] is True

    view_after = client.get(f"/api/allocation/{tx['id']}").json()
    assert "to_deposit" not in view_after["existing"][0]

    # Cleanup
    main.app.dependency_overrides = {}
    engine.dispose()


def test_patch_fund_updates_group(tmp_path):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.models  # noqa: F401
    import app.main as main
    from app.db import Base, get_db

    db_path = tmp_path / "test_fund_group.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    seed_session = TestSession()
    ensure_settings(seed_session)
    load_demo_data(seed_session)
    seed_session.close()

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides = {}
    main.app.dependency_overrides[get_db] = override_get_db

    client = TestClient(main.app)
    _authenticate(client)

    funds = client.get("/api/funds").json()
    assert funds, "demo data must create at least one fund"
    first = funds[0]
    fund_id = first["id"]
    original_group = first["group"]
    new_group = "wants" if original_group == "savings" else "savings"

    resp = client.patch(f"/api/funds/{fund_id}", json={
        "name": first["name"],
        "target_amount": str(first["target_amount"]),
        "monthly_contribution": str(first.get("monthly_contribution", "0")),
        "group": new_group,
    })
    assert resp.status_code == 200, f"PATCH failed: {resp.text}"
    assert resp.json()["group"] == new_group

    # Confirm via GET
    updated = next(f for f in client.get("/api/funds").json() if f["id"] == fund_id)
    assert updated["group"] == new_group

    main.app.dependency_overrides = {}
    engine.dispose()


def test_deposit_is_a_standalone_calculator(tmp_path):
    """Deposit settings persist (rate schedule, start date, term, contributions)
    and the calculator forecasts over the whole term — with no balance/contribute
    concept left, since it never touches real money or the budget."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.models  # noqa: F401
    import app.main as main
    from app.db import Base, get_db

    db_path = tmp_path / "test_deposit_calculator.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    seed_session = TestSession()
    ensure_settings(seed_session)
    load_demo_data(seed_session)
    seed_session.close()

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides = {}
    main.app.dependency_overrides[get_db] = override_get_db

    client = TestClient(main.app)
    _authenticate(client)

    assert "/api/deposit/contribute" not in {r.path for r in main.app.routes if hasattr(r, "path")}

    update_resp = client.post("/api/deposit", json={
        "rate": "10",
        "start_date": "2026-01-01",
        "term_months": 12,
        "initial_lump": "100000",
        "monthly_contribution": "5000",
        "rate_schedule": '[{"from": "2026-01-01", "rate": 10}, {"from": "2027-01-01", "rate": 12}]',
    })
    assert update_resp.status_code == 200, update_resp.text
    body = update_resp.json()
    assert body["term_months"] == 12
    assert body["initial_lump"] == 100000.0

    get_resp = client.get("/api/deposit")
    assert get_resp.json()["start_date"] == "2026-01-01"

    calc = client.get("/api/deposit/calculator").json()
    assert len(calc["rows"]) == 12
    assert calc["final_balance"] > 100000.0 + 5000 * 11, "interest + contributions must grow the total"

    main.app.dependency_overrides = {}
    engine.dispose()
