from __future__ import annotations
"""Sinking funds CRUD + contribute/spend."""

from datetime import date
date_type = date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.serializers import fund_dict, transaction_dict
from app.services.sinking_funds import SinkingFundService

router = APIRouter(prefix="/api/funds", tags=["funds"])


class FundBody(BaseModel):
    name: str
    target_amount: Decimal
    monthly_contribution: Decimal = Decimal("0")
    group: str = "savings"
    target_date: date | None = None
    is_rolling: bool = False


class ContributeBody(BaseModel):
    amount: Decimal
    date: date_type | None = None
    note: str | None = None


class SpendBody(BaseModel):
    amount: Decimal
    date: date_type | None = None
    category_id: int | None = None
    user_id: int | None = None
    comment: str | None = None


@router.get("")
def list_funds(db: Session = Depends(get_db)):
    return [fund_dict(f) for f in SinkingFundService.list_active(db)]


@router.post("")
def create_fund(body: FundBody, db: Session = Depends(get_db)):
    f = SinkingFundService.create(
        db,
        name=body.name,
        target_amount=body.target_amount,
        monthly_contribution=body.monthly_contribution,
        group=body.group,
        target_date=body.target_date,
        is_rolling=body.is_rolling,
    )
    return fund_dict(f)


@router.patch("/{fund_id}")
def update_fund(fund_id: int, body: FundBody, db: Session = Depends(get_db)):
    try:
        f = SinkingFundService.update(
            db,
            fund_id,
            name=body.name,
            target_amount=body.target_amount,
            monthly_contribution=body.monthly_contribution,
            target_date=body.target_date,
            is_rolling=body.is_rolling,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    return fund_dict(f)


@router.delete("/{fund_id}")
def delete_fund(fund_id: int, db: Session = Depends(get_db)):
    SinkingFundService.delete(db, fund_id)
    return {"ok": True}


@router.post("/{fund_id}/contribute")
def contribute(fund_id: int, body: ContributeBody, db: Session = Depends(get_db)):
    try:
        f = SinkingFundService.contribute(db, fund_id, body.amount, body.date or date.today(), body.note)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return fund_dict(f)


@router.post("/{fund_id}/spend")
def spend(fund_id: int, body: SpendBody, db: Session = Depends(get_db)):
    try:
        tx = SinkingFundService.spend_from_fund(
            db,
            fund_id,
            body.amount,
            body.date or date.today(),
            body.category_id,
            body.user_id,
            body.comment,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    return transaction_dict(tx)
