from __future__ import annotations
"""Goals CRUD + contribute + forecast."""

from datetime import date
date_type = date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Goal, GoalContribution
from app.serializers import goal_dict
from app.services.goals import (
    cascade_goal_scenario,
    goal_forecast_rows,
    months_to_goal_with_capitalization,
)

router = APIRouter(prefix="/api/goals", tags=["goals"])


class GoalBody(BaseModel):
    name: str
    target_amount: Decimal
    current_amount: Decimal | None = None
    deadline: date | None = None
    monthly_contribution: Decimal = Decimal("0")
    linked_account_name: str | None = None
    linked_category_id: int | None = None


class ContributeBody(BaseModel):
    amount: Decimal
    date: date_type | None = None
    comment: str | None = None


def _with_meta(db: Session, g: Goal) -> dict:
    d = goal_dict(g)
    d["months_to_goal"] = months_to_goal_with_capitalization(db, g)
    return d


@router.get("")
def list_goals(db: Session = Depends(get_db)):
    goals = db.query(Goal).filter(Goal.is_active.is_(True)).order_by(Goal.id).all()
    return [_with_meta(db, g) for g in goals]


@router.post("")
def create_goal(body: GoalBody, db: Session = Depends(get_db)):
    g = Goal(
        name=body.name,
        target_amount=body.target_amount,
        current_amount=body.current_amount or Decimal("0"),
        deadline=body.deadline,
        monthly_contribution=body.monthly_contribution,
        linked_account_name=body.linked_account_name,
        linked_category_id=body.linked_category_id,
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return _with_meta(db, g)


@router.patch("/{goal_id}")
def update_goal(goal_id: int, body: GoalBody, db: Session = Depends(get_db)):
    g = db.query(Goal).filter(Goal.id == goal_id).first()
    if not g:
        raise HTTPException(404, "goal not found")
    g.name = body.name
    g.target_amount = body.target_amount
    if body.current_amount is not None:
        g.current_amount = body.current_amount
    g.deadline = body.deadline
    g.monthly_contribution = body.monthly_contribution
    g.linked_account_name = body.linked_account_name
    g.linked_category_id = body.linked_category_id
    db.commit()
    db.refresh(g)
    return _with_meta(db, g)


@router.delete("/{goal_id}")
def delete_goal(goal_id: int, db: Session = Depends(get_db)):
    g = db.query(Goal).filter(Goal.id == goal_id).first()
    if g:
        g.is_active = False
        db.commit()
    return {"ok": True}


@router.post("/{goal_id}/contribute")
def contribute(goal_id: int, body: ContributeBody, db: Session = Depends(get_db)):
    g = db.query(Goal).filter(Goal.id == goal_id).first()
    if not g:
        raise HTTPException(404, "goal not found")
    g.current_amount += body.amount
    db.add(GoalContribution(goal_id=goal_id, amount=body.amount, date=body.date or date.today(), comment=body.comment))
    db.commit()
    db.refresh(g)
    return _with_meta(db, g)


@router.get("/{goal_id}/forecast")
def forecast(goal_id: int, months: int = 12, db: Session = Depends(get_db)):
    g = db.query(Goal).filter(Goal.id == goal_id).first()
    if not g:
        raise HTTPException(404, "goal not found")
    rows = goal_forecast_rows(db, g, g.monthly_contribution or Decimal("0"), months)
    current, increased = cascade_goal_scenario(db, g, Decimal("10000"))
    return {
        "rows": [{"date": d.isoformat(), "balance": float(b)} for d, b in rows],
        "months_current": current,
        "months_increased": increased,
    }
