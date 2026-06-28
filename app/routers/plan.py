from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.seed import GROUP_PERCENTS
from app.services.plan import PlanService
from app.templates_config import templates

router = APIRouter(prefix="/plan", tags=["plan"])


@router.get("/{year}/{month}", response_class=HTMLResponse)
def plan_page(request: Request, year: int, month: int, db: Session = Depends(get_db)):
    plan, categories = PlanService.get_plan_with_limits(db, year, month)
    limits_map = {}
    if plan:
        for lim in plan.limits:
            limits_map[lim.category_id] = lim.limit_amount

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
