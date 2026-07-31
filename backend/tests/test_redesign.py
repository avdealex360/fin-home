from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers models with Base.metadata before create_all
from app.db import Base
from tests.conftest import WS, create_workspace


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    create_workspace(session)  # id == WS
    yield session
    session.close()


def test_model_shape(db):
    import app.models as m

    # Goal is gone
    assert not hasattr(m, "Goal")
    assert not hasattr(m, "GoalContribution")

    # SinkingFund uses `group`, not `category_group`
    fund = m.SinkingFund(workspace_id=WS, name="Отпуск", target_amount=Decimal("50000"), group="savings")
    db.add(fund)
    db.commit()
    assert fund.group == "savings"
    assert not hasattr(fund, "category_group")

    # Income allocation feature is gone
    assert not hasattr(m, "IncomeAllocation")


from app.seed import ensure_workspace_settings, load_demo_data
from app.models import Category, SinkingFund, Setting


def test_seed_has_savings_category_no_goals(db):
    ensure_workspace_settings(db, WS)
    load_demo_data(db, WS)

    groups = {c.group for c in db.query(Category).all()}
    assert "savings" in groups, "a savings category must exist so limits/spend can be tracked like needs/wants"
    assert groups <= {"needs", "wants", "savings", "income"}

    funds = db.query(SinkingFund).all()
    assert funds, "demo should create копилки"
    assert all(f.group in ("wants", "savings") for f in funds)
    assert any(f.group == "savings" for f in funds)

    assert (
        db.query(Setting)
        .filter(Setting.workspace_id == WS, Setting.key == "deposit_monthly_target")
        .first()
        is not None
    )


from app.models import Transaction, MonthlyPlan
from app.services.sinking_funds import SinkingFundService


def test_fund_create_and_spend_with_group(db):
    f = SinkingFundService.create(db, WS, name="Отпуск", target_amount=Decimal("100000"),
                                  monthly_contribution=Decimal("8000"), group="wants")
    assert f.group == "wants"
    SinkingFundService.contribute(db, WS, f.id, Decimal("8000"), date.today())
    tx = SinkingFundService.spend_from_fund(db, WS, f.id, Decimal("3000"), date.today(),
                                            category_id=None, user_id=None, comment=None)
    db.refresh(f)
    assert f.current_amount == Decimal("5000")
    assert tx.is_sinking_fund_spend and tx.fund_id == f.id
    assert tx.workspace_id == WS


def test_dashboard_savings_counts_fund_contributions(db):
    """Savings.spent must count копилка contributions — the вклад calculator has
    no ledger at all anymore, so it structurally cannot move this number."""
    ensure_workspace_settings(db, WS); load_demo_data(db, WS)
    from app.services.dashboard import DashboardService

    y, mth = date.today().year, date.today().month
    db.add(Transaction(workspace_id=WS, type="income", amount=Decimal("100000"), date=date.today()))
    db.commit()

    fund = db.query(SinkingFund).filter(SinkingFund.group == "savings").first()
    assert fund, "demo data must include a savings копилка"
    SinkingFundService.contribute(db, WS, fund.id, Decimal("5000"), date.today())

    s = DashboardService.get_month_summary(db, WS, y, mth)
    sav = next(g for g in s.groups if g.name == "savings")
    assert sav.spent == Decimal("5000")
    assert {g.name for g in s.groups} == {"needs", "wants", "savings"}
    assert not hasattr(s, "goals") or s.goals == []


def test_savings_category_limit_shows_up_in_group_limit(db):
    """A CategoryLimit on a savings-group category must reach Dashboard's group.limit,
    exactly like needs/wants — this was the bug: savings limits were entered but ignored."""
    ensure_workspace_settings(db, WS); load_demo_data(db, WS)
    from app.services.dashboard import DashboardService
    from app.services.plan import PlanService

    y, mth = date.today().year, date.today().month
    cat = db.query(Category).filter(Category.group == "savings").first()
    assert cat, "demo data must seed a savings category"

    PlanService.get_or_create_plan(db, WS, y, mth)
    PlanService.save_plan(db, WS, y, mth, Decimal("100000"), category_limits={cat.id: Decimal("20000")})

    s = DashboardService.get_month_summary(db, WS, y, mth)
    sav = next(g for g in s.groups if g.name == "savings")
    assert sav.limit == Decimal("20000")

    meter = PlanService.meter_503020(db, WS, y, mth)
    assert meter["savings"]["allocated"] == 20000.0


def test_analytics_has_503020_split(db):
    ensure_workspace_settings(db, WS); load_demo_data(db, WS)
    from app.services.analytics import AnalyticsService
    from app.util import period_date_range
    y, mth = date.today().year, date.today().month
    start, end = period_date_range(y, mth, "month")
    data = AnalyticsService.split_503020(db, WS, start, end)
    assert set(data.keys()) == {"needs", "wants", "savings"}
    assert set(data["needs"].keys()) == {"fact", "ideal", "percent"}


def test_plan_meter_needs_target(db):
    ensure_workspace_settings(db, WS); load_demo_data(db, WS)
    from app.services.plan import PlanService
    y, mth = date.today().year, date.today().month
    plan = PlanService.get_or_create_plan(db, WS, y, mth)
    plan.expected_income = Decimal("100000"); db.commit()

    meter = PlanService.meter_503020(db, WS, y, mth)
    assert abs(meter["needs"]["target"] - 50000) < 1


def _demo(api):
    api.client.post("/api/onboarding", json={"mode": "demo"})


def test_api_contract(api):
    client = api.client
    _demo(api)

    assert client.get("/api/goals").status_code in (404, 405)

    f = client.get("/api/funds").json()[0]
    assert "group" in f and "category_group" not in f

    dep = client.get("/api/deposit").json()
    assert "term_months" in dep and "balance" not in dep

    # Income lands on the balance as-is — no allocation step, no leftover fields.
    tx = client.post("/api/transactions", json={"type": "income", "amount": 30000,
                                                "date": str(date.today())}).json()
    assert "unallocated" not in tx and "is_fully_allocated" not in tx
    assert client.get(f"/api/allocation/{tx['id']}").status_code in (404, 405)

    summary = client.get("/api/dashboard").json()
    assert summary["income_fact"] == 30000.0
    assert "unallocated" not in summary


def test_patch_fund_updates_group(api):
    client = api.client
    _demo(api)

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

    updated = next(f for f in client.get("/api/funds").json() if f["id"] == fund_id)
    assert updated["group"] == new_group


def test_deposit_is_a_standalone_calculator(api):
    """Deposit settings persist (rate schedule, start date, term, contributions)
    and the calculator forecasts over the whole term — with no balance/contribute
    concept left, since it never touches real money or the budget."""
    client = api.client
    _demo(api)
    import app.main as main

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


def test_transactions_list_pagination_filter_sort(api):
    """GET /api/transactions supports offset pagination, type/category filters,
    and sorting — needed by the full transactions history page."""
    client = api.client
    _demo(api)

    cat_id = client.get("/api/categories").json()[0]["id"]
    for i, amount in enumerate([1000, 2000, 3000]):
        client.post("/api/transactions", json={
            "type": "expense", "amount": amount, "category_id": cat_id,
            "date": f"2026-07-0{i + 1}",
        })

    all_resp = client.get("/api/transactions").json()
    assert all_resp["total"] == 3
    assert len(all_resp["items"]) == 3

    page1 = client.get("/api/transactions?limit=2&offset=0").json()
    page2 = client.get("/api/transactions?limit=2&offset=2").json()
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 1
    assert page1["total"] == page2["total"] == 3

    by_amount_asc = client.get("/api/transactions?sort_by=amount&sort_dir=asc").json()
    assert [i["amount"] for i in by_amount_asc["items"]] == [1000, 2000, 3000]

    by_category = client.get(f"/api/transactions?category_id={cat_id}").json()
    assert by_category["total"] == 3
    other_cat = client.get("/api/categories").json()[1]["id"]
    by_other_category = client.get(f"/api/transactions?category_id={other_cat}").json()
    assert by_other_category["total"] == 0


def test_analytics_period_switch_aggregates_quarter_and_year(api):
    """period=quarter/year must sum transactions across the whole range, not
    just the anchor month — this is what backs the Analytics period toggle."""
    client = api.client
    _demo(api)

    cat_id = client.get("/api/categories").json()[0]["id"]
    # One expense in each month of Q1 2026.
    for m in (1, 2, 3):
        client.post("/api/transactions", json={
            "type": "expense", "amount": 1000, "category_id": cat_id, "date": f"2026-{m:02d}-15",
        })

    month_resp = client.get("/api/analytics?year=2026&month=2&period=month").json()
    quarter_resp = client.get("/api/analytics?year=2026&month=2&period=quarter").json()

    month_top = {t["name"]: t["amount"] for t in month_resp["top_categories"]}
    quarter_top = {t["name"]: t["amount"] for t in quarter_resp["top_categories"]}
    cat_name = client.get("/api/categories").json()[0]["name"]

    assert month_top.get(cat_name) == 1000
    assert quarter_top.get(cat_name) == 3000
    assert quarter_resp["range"]["start"] == "2026-01-01"
    assert quarter_resp["range"]["end"] == "2026-03-31"
