from __future__ import annotations
"""Income allocation: suggested buckets (50/30/20) + saving the user's distribution."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import IncomeAllocation, Transaction
from app.services.allocation import (
    AllocationInput,
    allocate_income,
    get_allocation_buckets,
    get_unallocated_for_tx,
)

router = APIRouter(prefix="/api/allocation", tags=["allocation"])


@router.get("/{tx_id}")
def allocation_view(tx_id: int, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx or tx.type != "income":
        raise HTTPException(404, "income transaction not found")

    buckets = get_allocation_buckets(db, tx.date.year, tx.date.month, tx.amount)
    existing = db.query(IncomeAllocation).filter(IncomeAllocation.income_tx_id == tx_id).all()
    return {
        "transaction": {
            "id": tx.id,
            "amount": float(tx.amount),
            "date": tx.date.isoformat(),
            "is_fully_allocated": tx.is_fully_allocated,
        },
        "unallocated": float(get_unallocated_for_tx(db, tx)),
        "buckets": [
            {
                "group": b.group,
                "label": b.label,
                "percent": b.percent,
                "target_amount": float(b.target_amount),
                "items": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "kind": item.kind,
                        "suggested_amount": float(item.suggested_amount),
                        "group": item.group,
                    }
                    for item in b.items
                ],
            }
            for b in buckets
        ],
        "existing": [
            {
                "category_id": a.category_id,
                "fund_id": a.fund_id,
                "amount": float(a.amount),
                "to_deposit": a.to_deposit,
            }
            for a in existing
        ],
    }


class AllocItem(BaseModel):
    category_id: int | None = None
    fund_id: int | None = None
    to_deposit: bool = False
    amount: Decimal = Decimal("0")
    group: str = "needs"


class AllocateBody(BaseModel):
    allocations: list[AllocItem]


@router.post("/{tx_id}")
def allocate(tx_id: int, body: AllocateBody, db: Session = Depends(get_db)):
    inputs = [
        AllocationInput(
            category_id=i.category_id,
            fund_id=i.fund_id,
            to_deposit=i.to_deposit,
            amount=i.amount,
            group=i.group,
        )
        for i in body.allocations
    ]
    try:
        tx = allocate_income(db, tx_id, inputs)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "id": tx.id,
        "is_fully_allocated": tx.is_fully_allocated,
        "unallocated": float(get_unallocated_for_tx(db, tx)),
    }
