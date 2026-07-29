from __future__ import annotations
"""Monthly plan: limits, planned expenses/debt payments."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import ym_params
from app.db import get_db
from app.serializers import plan_dict
from app.services.plan import PlanService

router = APIRouter(prefix="/api/plan", tags=["plan"])


class SavePlanBody(BaseModel):
    expected_income: Decimal


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
    return plan_dict(plan, PlanService.spent_by_category(db, year, month))


@router.get("/{year}/{month}/meter")
def get_meter(year: int, month: int, db: Session = Depends(get_db)):
    return PlanService.meter_503020(db, year, month)


@router.post("")
def save_plan(
    body: SavePlanBody,
    ym: tuple[int, int] = Depends(ym_params),
    db: Session = Depends(get_db),
):
    year, month = ym
    plan = PlanService.save_plan(db, year, month, body.expected_income)
    return plan_dict(plan, PlanService.spent_by_category(db, year, month))


@router.post("/limits")
def save_limits(
    body: LimitsBody,
    ym: tuple[int, int] = Depends(ym_params),
    db: Session = Depends(get_db),
):
    year, month = ym
    plan = PlanService.get_or_create_plan(db, year, month)
    PlanService.save_plan(db, year, month, plan.expected_income, category_limits=body.limits)
    db.refresh(plan)
    return plan_dict(plan, PlanService.spent_by_category(db, year, month))


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
    return plan_dict(plan, PlanService.spent_by_category(db, year, month))


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
    return plan_dict(plan, PlanService.spent_by_category(db, year, month))


@router.delete("/planned-debt/{payment_id}")
def delete_planned_debt(payment_id: int, db: Session = Depends(get_db)):
    PlanService.delete_planned_debt_payment(db, payment_id)
    return {"ok": True}
