from __future__ import annotations
"""Debts CRUD + payments + cost analysis."""

from datetime import date
date_type = date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import ws_id
from app.db import get_db
from app.models import Debt, DebtPayment
from app.serializers import debt_dict, debt_payment_dict
from app.services.debts import compute_priority_ranks, debt_cost_analysis, get_active_debts_sorted

router = APIRouter(prefix="/api/debts", tags=["debts"])


class DebtBody(BaseModel):
    name: str
    total_amount: Decimal
    remaining: Decimal | None = None
    monthly_payment: Decimal = Decimal("0")
    interest_rate: Decimal = Decimal("0")
    type: str = "loan"  # credit_card | split | loan
    start_date: date | None = None
    target_close_date: date | None = None
    grace_period_end: date | None = None
    next_payment_date: date | None = None


class PaymentBody(BaseModel):
    amount: Decimal
    date: date_type | None = None
    comment: str | None = None


@router.get("")
def list_debts(include_closed: bool = False, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    if include_closed:
        debts = (
            db.query(Debt)
            .filter(Debt.workspace_id == ws)
            .order_by(Debt.is_closed, Debt.id)
            .all()
        )
        return [debt_dict(d) for d in debts]
    return [debt_dict(d) for d in get_active_debts_sorted(db, ws)]


@router.post("")
def create_debt(body: DebtBody, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    d = Debt(
        workspace_id=ws,
        name=body.name,
        total_amount=body.total_amount,
        remaining=body.remaining if body.remaining is not None else body.total_amount,
        monthly_payment=body.monthly_payment,
        interest_rate=body.interest_rate,
        type=body.type,
        start_date=body.start_date or date.today(),
        target_close_date=body.target_close_date,
        grace_period_end=body.grace_period_end,
        next_payment_date=body.next_payment_date,
    )
    db.add(d)
    db.commit()
    compute_priority_ranks(db, ws)
    db.refresh(d)
    return debt_dict(d)


@router.patch("/{debt_id}")
def update_debt(debt_id: int, body: DebtBody, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    d = db.query(Debt).filter(Debt.id == debt_id, Debt.workspace_id == ws).first()
    if not d:
        raise HTTPException(404, "debt not found")
    d.name = body.name
    d.total_amount = body.total_amount
    if body.remaining is not None:
        d.remaining = body.remaining
    d.monthly_payment = body.monthly_payment
    d.interest_rate = body.interest_rate
    d.type = body.type
    d.start_date = body.start_date
    d.target_close_date = body.target_close_date
    d.grace_period_end = body.grace_period_end
    d.next_payment_date = body.next_payment_date
    db.commit()
    compute_priority_ranks(db, ws)
    db.refresh(d)
    return debt_dict(d)


@router.delete("/{debt_id}")
def delete_debt(debt_id: int, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    d = db.query(Debt).filter(Debt.id == debt_id, Debt.workspace_id == ws).first()
    if d:
        db.delete(d)
        db.commit()
    return {"ok": True}


@router.post("/{debt_id}/close")
def close_debt(debt_id: int, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    d = db.query(Debt).filter(Debt.id == debt_id, Debt.workspace_id == ws).first()
    if not d:
        raise HTTPException(404, "debt not found")
    d.is_closed = True
    d.remaining = Decimal("0")
    db.commit()
    db.refresh(d)
    return debt_dict(d)


@router.post("/{debt_id}/payment")
def add_payment(debt_id: int, body: PaymentBody, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    d = db.query(Debt).filter(Debt.id == debt_id, Debt.workspace_id == ws).first()
    if not d:
        raise HTTPException(404, "debt not found")
    db.add(DebtPayment(debt_id=debt_id, amount=body.amount, date=body.date or date.today(), comment=body.comment))
    d.remaining = max(d.remaining - body.amount, Decimal("0"))
    if d.remaining == 0:
        d.is_closed = True
    db.commit()
    db.refresh(d)
    return debt_dict(d)


@router.get("/{debt_id}/payments")
def list_payments(debt_id: int, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    rows = (
        db.query(DebtPayment)
        .join(Debt, Debt.id == DebtPayment.debt_id)
        .filter(DebtPayment.debt_id == debt_id, Debt.workspace_id == ws)
        .order_by(DebtPayment.date.desc())
        .all()
    )
    return [debt_payment_dict(p) for p in rows]


@router.get("/{debt_id}/cost-analysis")
def cost_analysis(debt_id: int, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    analysis = debt_cost_analysis(db, ws, debt_id)
    if not analysis:
        raise HTTPException(404, "debt not found or closed")
    return analysis
