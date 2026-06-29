from __future__ import annotations
"""Monthly plan: limits, planned expenses/debt payments, close month."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import ym_params
from app.db import get_db
from app.serializers import plan_dict
from app.services.allocation import close_month
from app.services.plan import PlanService

router = APIRouter(prefix="/api/plan", tags=["plan"])


class SavePlanBody(BaseModel):
    expected_income: Decimal
    auto_distribute: bool = True


class LimitsBody(BaseModel):
    limits: dict[int, Decimal]  # category_id -> amount


class PlannedExpenseBody(BaseModel):
    description: str
    amount: Decimal
    category_id: int | None = None
    expected_date: date | None = None


class PlannedDebtBody(BaseModel):
    debt_id: int
    amount: Decimal


@router.get("")
def get_plan(ym: tuple[int, int] = Depends(ym_params), db: Session = Depends(get_db)):
    year, month = ym
    plan = PlanService.get_or_create_plan(db, year, month)
    return plan_dict(plan)


@router.post("")
def save_plan(
    body: SavePlanBody,
    ym: tuple[int, int] = Depends(ym_params),
    db: Session = Depends(get_db),
):
    year, month = ym
    plan = PlanService.save_plan(
        db, year, month, body.expected_income, auto_distribute=body.auto_distribute
    )
    return plan_dict(plan)


@router.post("/limits")
def save_limits(
    body: LimitsBody,
    ym: tuple[int, int] = Depends(ym_params),
    db: Session = Depends(get_db),
):
    year, month = ym
    plan = PlanService.get_or_create_plan(db, year, month)
    PlanService.save_plan(
        db, year, month, plan.expected_income, category_limits=body.limits, auto_distribute=False
    )
    db.refresh(plan)
    return plan_dict(plan)


@router.post("/planned-expense")
def add_planned_expense(
    body: PlannedExpenseBody,
    ym: tuple[int, int] = Depends(ym_params),
    db: Session = Depends(get_db),
):
    year, month = ym
    plan = PlanService.get_or_create_plan(db, year, month)
    PlanService.add_planned_expense(
        db, plan.id, body.description, body.amount, body.category_id, body.expected_date
    )
    db.refresh(plan)
    return plan_dict(plan)


@router.delete("/planned-expense/{expense_id}")
def delete_planned_expense(expense_id: int, db: Session = Depends(get_db)):
    PlanService.delete_planned_expense(db, expense_id)
    return {"ok": True}


@router.post("/planned-debt")
def add_planned_debt(
    body: PlannedDebtBody,
    ym: tuple[int, int] = Depends(ym_params),
    db: Session = Depends(get_db),
):
    year, month = ym
    plan = PlanService.get_or_create_plan(db, year, month)
    PlanService.add_planned_debt_payment(db, plan.id, body.debt_id, body.amount)
    db.refresh(plan)
    return plan_dict(plan)


@router.delete("/planned-debt/{payment_id}")
def delete_planned_debt(payment_id: int, db: Session = Depends(get_db)):
    PlanService.delete_planned_debt_payment(db, payment_id)
    return {"ok": True}


@router.post("/close")
def close(ym: tuple[int, int] = Depends(ym_params), db: Session = Depends(get_db)):
    year, month = ym
    try:
        plan = close_month(db, year, month)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return plan_dict(plan)
