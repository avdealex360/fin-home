from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Goal, GoalContribution
from app.templates_config import templates

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("/", response_class=HTMLResponse)
def goals_page(request: Request, db: Session = Depends(get_db)):
    goals = db.query(Goal).filter(Goal.is_active.is_(True)).order_by(Goal.id).all()
    return templates.TemplateResponse(request, "goals.html", {"goals": goals, "today": date.today().isoformat()})


@router.post("/")
def create_goal(
    name: str = Form(...),
    target_amount: str = Form(...),
    current_amount: str = Form("0"),
    deadline: str = Form(""),
    monthly_contribution: str = Form("0"),
    linked_account_name: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        target = Decimal(target_amount.replace(",", ".").replace(" ", ""))
        current = Decimal(current_amount.replace(",", ".").replace(" ", ""))
        monthly = Decimal(monthly_contribution.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return RedirectResponse("/goals?error=1", status_code=303)

    goal = Goal(
        name=name,
        target_amount=target,
        current_amount=current,
        deadline=date.fromisoformat(deadline) if deadline else None,
        monthly_contribution=monthly,
        linked_account_name=linked_account_name or None,
    )
    db.add(goal)
    db.commit()
    return RedirectResponse("/goals?saved=1", status_code=303)


@router.post("/{goal_id}/contribute")
def contribute(
    goal_id: int,
    amount: str = Form(...),
    date_str: str = Form(..., alias="date"),
    comment: str = Form(""),
    db: Session = Depends(get_db),
):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        return RedirectResponse("/goals", status_code=303)
    amt = Decimal(amount.replace(",", ".").replace(" ", ""))
    goal.current_amount += amt
    db.add(GoalContribution(goal_id=goal_id, amount=amt, date=date.fromisoformat(date_str), comment=comment or None))
    db.commit()
    return RedirectResponse("/goals?saved=1", status_code=303)


@router.post("/{goal_id}/update")
def update_goal(
    goal_id: int,
    name: str = Form(...),
    target_amount: str = Form(...),
    current_amount: str = Form(...),
    deadline: str = Form(""),
    monthly_contribution: str = Form("0"),
    db: Session = Depends(get_db),
):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        return RedirectResponse("/goals", status_code=303)
    goal.name = name
    goal.target_amount = Decimal(target_amount.replace(",", ".").replace(" ", ""))
    goal.current_amount = Decimal(current_amount.replace(",", ".").replace(" ", ""))
    goal.deadline = date.fromisoformat(deadline) if deadline else None
    goal.monthly_contribution = Decimal(monthly_contribution.replace(",", ".").replace(" ", ""))
    db.commit()
    return RedirectResponse("/goals?saved=1", status_code=303)


@router.post("/{goal_id}/delete")
def delete_goal(goal_id: int, db: Session = Depends(get_db)):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if goal:
        goal.is_active = False
        db.commit()
    return RedirectResponse("/goals", status_code=303)
