from __future__ import annotations
"""Monthly plan: limits, planned expenses/debt payments."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import ws_id, ym_params
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
def get_plan(
    ym: tuple[int, int] = Depends(ym_params),
    db: Session = Depends(get_db),
    ws: int = Depends(ws_id),
):
    year, month = ym
    plan = PlanService.get_or_create_plan(db, ws, year, month)
    return plan_dict(plan, PlanService.spent_by_category(db, ws, year, month))


@router.get("/{year}/{month}/meter")
def get_meter(year: int, month: int, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    return PlanService.meter_503020(db, ws, year, month)


@router.post("")
def save_plan(
    body: SavePlanBody,
    ym: tuple[int, int] = Depends(ym_params),
    db: Session = Depends(get_db),
    ws: int = Depends(ws_id),
):
    year, month = ym
    plan = PlanService.save_plan(db, ws, year, month, body.expected_income)
    return plan_dict(plan, PlanService.spent_by_category(db, ws, year, month))


@router.post("/limits")
def save_limits(
    body: LimitsBody,
    ym: tuple[int, int] = Depends(ym_params),
    db: Session = Depends(get_db),
    ws: int = Depends(ws_id),
):
    year, month = ym
    plan = PlanService.get_or_create_plan(db, ws, year, month)
    PlanService.save_plan(db, ws, year, month, plan.expected_income, category_limits=body.limits)
    db.refresh(plan)
    return plan_dict(plan, PlanService.spent_by_category(db, ws, year, month))


@router.post("/planned-expense")
def add_planned_expense(
    body: PlannedExpenseBody,
    ym: tuple[int, int] = Depends(ym_params),
    db: Session = Depends(get_db),
    ws: int = Depends(ws_id),
):
    year, month = ym
    plan = PlanService.get_or_create_plan(db, ws, year, month)
    PlanService.add_planned_expense(
        db, plan.id, body.description, body.amount, body.category_id, body.expected_date
    )
    db.refresh(plan)
    return plan_dict(plan, PlanService.spent_by_category(db, ws, year, month))


@router.delete("/planned-expense/{expense_id}")
def delete_planned_expense(expense_id: int, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    PlanService.delete_planned_expense(db, ws, expense_id)
    return {"ok": True}


@router.post("/planned-debt")
def add_planned_debt(
    body: PlannedDebtBody,
    ym: tuple[int, int] = Depends(ym_params),
    db: Session = Depends(get_db),
    ws: int = Depends(ws_id),
):
    year, month = ym
    plan = PlanService.get_or_create_plan(db, ws, year, month)
    PlanService.add_planned_debt_payment(db, plan.id, body.debt_id, body.amount)
    db.refresh(plan)
    return plan_dict(plan, PlanService.spent_by_category(db, ws, year, month))


@router.delete("/planned-debt/{payment_id}")
def delete_planned_debt(payment_id: int, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    PlanService.delete_planned_debt_payment(db, ws, payment_id)
    return {"ok": True}
