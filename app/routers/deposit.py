from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DepositSnapshot, Goal
from app.services.plan import DepositService
from app.templates_config import templates

router = APIRouter(prefix="/deposit", tags=["deposit"])


@router.get("/", response_class=HTMLResponse)
def deposit_page(
    request: Request,
    contribution: str = "0",
    db: Session = Depends(get_db),
):
    balance, rate = DepositService.get_current(db)
    goal = db.query(Goal).filter(Goal.name == "Машина").first()
    target_date = goal.deadline if goal and goal.deadline else date(2027, 12, 31)
    target_amount = goal.target_amount if goal else Decimal("1500000")

    try:
        monthly = Decimal(contribution.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        monthly = Decimal("0")

    forecast = DepositService.forecast(balance, rate, monthly, target_date)
    required = DepositService.required_monthly(balance, rate, target_amount, target_date)
    snapshots = db.query(DepositSnapshot).order_by(DepositSnapshot.date.desc()).limit(12).all()
    final = forecast[-1][1] if forecast else balance

    return templates.TemplateResponse(
        request,
        "deposit.html",
        {
            "balance": balance,
            "rate": rate,
            "monthly": monthly,
            "target_date": target_date,
            "target_amount": target_amount,
            "forecast": forecast,
            "required": required,
            "snapshots": snapshots,
            "final": final,
            "today": date.today(),
        },
    )


@router.post("/update")
def update_deposit(
    balance: str = Form(...),
    rate: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        bal = Decimal(balance.replace(",", ".").replace(" ", ""))
        r = Decimal(rate.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return RedirectResponse("/deposit?error=1", status_code=303)

    DepositService.update(db, bal, r)
    db.add(DepositSnapshot(balance=bal, rate=r, date=date.today()))
    db.commit()
    return RedirectResponse("/deposit?saved=1", status_code=303)


@router.get("/calculator", response_class=HTMLResponse)
def calculator_partial(
    request: Request,
    contribution: str = "0",
    db: Session = Depends(get_db),
):
    balance, rate = DepositService.get_current(db)
    goal = db.query(Goal).filter(Goal.name == "Машина").first()
    target_date = goal.deadline if goal and goal.deadline else date(2027, 12, 31)

    try:
        monthly = Decimal(contribution.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        monthly = Decimal("0")

    forecast = DepositService.forecast(balance, rate, monthly, target_date)
    final = forecast[-1][1] if forecast else balance

    return templates.TemplateResponse(
        request,
        "partials/deposit_calculator.html",
        {"monthly": monthly, "final": final, "forecast": forecast},
    )
