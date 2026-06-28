from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import Debt, PlannedDebtPayment
from app.seed import GROUP_PERCENTS
from app.services.plan import PlanService
from app.templates_config import templates

router = APIRouter(prefix="/plan", tags=["plan"])


@router.get("", response_class=RedirectResponse)
def plan_current():
    today = date.today()
    return RedirectResponse(f"/plan/{today.year}/{today.month}", status_code=303)


@router.get("/{year}/{month}", response_class=HTMLResponse)
def plan_page(request: Request, year: int, month: int, db: Session = Depends(get_db)):
    if month < 1 or month > 12:
        today = date.today()
        return RedirectResponse(f"/plan/{today.year}/{today.month}", status_code=303)
    from app.models import MonthlyPlan

    plan = (
        db.query(MonthlyPlan)
        .options(
            joinedload(MonthlyPlan.limits),
            joinedload(MonthlyPlan.planned_expenses),
            joinedload(MonthlyPlan.planned_debt_payments).joinedload(PlannedDebtPayment.debt),
        )
        .filter(MonthlyPlan.year == year, MonthlyPlan.month == month)
        .first()
    )
    _, categories = PlanService.get_plan_with_limits(db, year, month)
    limits_map = {}
    if plan:
        for lim in plan.limits:
            limits_map[lim.category_id] = lim.limit_amount

    debts = db.query(Debt).filter(Debt.is_closed.is_(False)).order_by(Debt.id).all()

    from app.templates_config import _shift_month

    prev_year, prev_month = _shift_month(year, month, -1)
    next_year, next_month = _shift_month(year, month, 1)
    today = date.today()

    return templates.TemplateResponse(
        request,
        "plan.html",
        {
            "year": year,
            "month": month,
            "plan": plan,
            "categories": categories,
            "limits_map": limits_map,
            "group_percents": GROUP_PERCENTS,
            "debts": debts,
            "today": today.isoformat(),
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
            "is_current_month": year == today.year and month == today.month,
        },
    )


@router.post("/{year}/{month}")
def save_plan(
    year: int,
    month: int,
    expected_income: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        income = Decimal(expected_income.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return RedirectResponse(f"/plan/{year}/{month}?error=1", status_code=303)

    PlanService.save_plan(db, year, month, income, auto_distribute=True)
    return RedirectResponse(f"/plan/{year}/{month}?saved=1", status_code=303)


@router.post("/{year}/{month}/limits")
async def save_limits(
    request: Request,
    year: int,
    month: int,
    expected_income: str = Form(...),
    db: Session = Depends(get_db),
):
    form = await request.form()
    try:
        income = Decimal(str(form.get("expected_income", "0")).replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        income = Decimal("0")

    category_limits: dict[int, Decimal] = {}
    for key, value in form.items():
        if key.startswith("limit_"):
            cat_id = int(key.replace("limit_", ""))
            try:
                category_limits[cat_id] = Decimal(str(value).replace(",", ".").replace(" ", ""))
            except InvalidOperation:
                pass

    PlanService.save_plan(db, year, month, income, category_limits=category_limits, auto_distribute=False)
    return RedirectResponse(f"/plan/{year}/{month}?saved=1", status_code=303)


@router.post("/{year}/{month}/planned-expense")
def add_planned_expense(
    year: int,
    month: int,
    description: str = Form(...),
    amount: str = Form(...),
    category_id: str = Form(""),
    expected_date: str = Form(""),
    db: Session = Depends(get_db),
):
    plan = PlanService.get_or_create_plan(db, year, month)
    try:
        amt = Decimal(amount.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return RedirectResponse(f"/plan/{year}/{month}?error=1", status_code=303)

    PlanService.add_planned_expense(
        db,
        plan.id,
        description,
        amt,
        int(category_id) if category_id else None,
        date.fromisoformat(expected_date) if expected_date else None,
    )
    return RedirectResponse(f"/plan/{year}/{month}?saved=1", status_code=303)


@router.post("/{year}/{month}/planned-debt")
def add_planned_debt(
    year: int,
    month: int,
    debt_id: int = Form(...),
    amount: str = Form(...),
    db: Session = Depends(get_db),
):
    plan = PlanService.get_or_create_plan(db, year, month)
    try:
        amt = Decimal(amount.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return RedirectResponse(f"/plan/{year}/{month}?error=1", status_code=303)

    PlanService.add_planned_debt_payment(db, plan.id, debt_id, amt)
    return RedirectResponse(f"/plan/{year}/{month}?saved=1", status_code=303)


@router.post("/planned-expense/{expense_id}/delete")
def delete_planned_expense(expense_id: int, db: Session = Depends(get_db)):
    from app.models import PlannedExpense

    item = db.query(PlannedExpense).filter(PlannedExpense.id == expense_id).first()
    year, month = date.today().year, date.today().month
    if item and item.plan:
        year, month = item.plan.year, item.plan.month
    PlanService.delete_planned_expense(db, expense_id)
    return RedirectResponse(f"/plan/{year}/{month}", status_code=303)


@router.post("/planned-debt/{payment_id}/delete")
def delete_planned_debt(payment_id: int, db: Session = Depends(get_db)):
    from app.models import PlannedDebtPayment

    item = db.query(PlannedDebtPayment).filter(PlannedDebtPayment.id == payment_id).first()
    year, month = date.today().year, date.today().month
    if item and item.plan:
        year, month = item.plan.year, item.plan.month
    PlanService.delete_planned_debt_payment(db, payment_id)
    return RedirectResponse(f"/plan/{year}/{month}", status_code=303)
