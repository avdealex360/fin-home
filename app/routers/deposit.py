from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DepositSnapshot, Goal
from app.services.settings_store import get_setting, set_setting
from app.services.plan import DepositService
from app.templates_config import templates

router = APIRouter(prefix="/deposit", tags=["deposit"])


def _deposit_context(db: Session, monthly: Decimal, target_date: date) -> dict:
    settings = DepositService.get_settings(db)
    balance, rate = settings["balance"], settings["rate"]
    goal = db.query(Goal).filter(Goal.name == "Машина").first()
    target_amount = goal.target_amount if goal else Decimal("1500000")

    detailed = DepositService.forecast_detailed(db, monthly, target_date)
    forecast = [(r.date, r.balance_after) for r in detailed]
    final = forecast[-1][1] if forecast else balance

    required = DepositService.required_monthly(
        balance,
        rate,
        target_amount,
        target_date,
        start_date=date.today(),
        rate_schedule=settings["rate_schedule"],
        capitalization_day=settings["cap_day"],
    )

    snapshots = db.query(DepositSnapshot).order_by(DepositSnapshot.date.desc()).limit(12).all()

    return {
        "balance": balance,
        "rate": rate,
        "monthly": monthly,
        "target_date": target_date,
        "target_amount": target_amount,
        "forecast": forecast,
        "detailed": detailed,
        "required": required,
        "snapshots": snapshots,
        "final": final,
        "today": date.today(),
        "cap_day": settings["cap_day"],
        "start_date": settings["start_date"],
        "rate_schedule_raw": get_setting(db, "deposit_rate_schedule", ""),
        "initial_lump": get_setting(db, "deposit_initial_lump", "0"),
        "chart_forecast_labels": [p[0].strftime("%d.%m.%Y") for p in forecast],
        "chart_forecast_values": [float(p[1]) for p in forecast],
    }


@router.get("/", response_class=HTMLResponse)
def deposit_page(
    request: Request,
    contribution: str = "0",
    db: Session = Depends(get_db),
):
    goal = db.query(Goal).filter(Goal.name == "Машина").first()
    target_date = goal.deadline if goal and goal.deadline else date(2027, 12, 31)
    try:
        monthly = Decimal(contribution.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        monthly = Decimal("0")

    return templates.TemplateResponse(
        request, "deposit.html", _deposit_context(db, monthly, target_date)
    )


@router.post("/update")
def update_deposit(
    balance: str = Form(...),
    rate: str = Form(...),
    cap_day: str = Form("18"),
    start_date: str = Form(""),
    initial_lump: str = Form("0"),
    rate_schedule: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        bal = Decimal(balance.replace(",", ".").replace(" ", ""))
        r = Decimal(rate.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return RedirectResponse("/deposit?error=1", status_code=303)

    DepositService.update(db, bal, r)
    set_setting(db, "deposit_cap_day", cap_day or "18")
    if start_date:
        set_setting(db, "deposit_start_date", start_date)
    set_setting(db, "deposit_initial_lump", initial_lump or "0")
    set_setting(db, "deposit_rate_schedule", rate_schedule or "")
    db.add(DepositSnapshot(balance=bal, rate=r, date=date.today()))
    db.commit()
    return RedirectResponse("/deposit?saved=1", status_code=303)


@router.get("/calculator", response_class=HTMLResponse)
def calculator_partial(
    request: Request,
    contribution: str = "0",
    db: Session = Depends(get_db),
):
    goal = db.query(Goal).filter(Goal.name == "Машина").first()
    target_date = goal.deadline if goal and goal.deadline else date(2027, 12, 31)
    try:
        monthly = Decimal(contribution.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        monthly = Decimal("0")

    ctx = _deposit_context(db, monthly, target_date)
    return templates.TemplateResponse(
        request,
        "partials/deposit_calculator.html",
        {"monthly": monthly, "final": ctx["final"], "forecast": ctx["forecast"]},
    )
