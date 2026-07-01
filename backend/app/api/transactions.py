from __future__ import annotations
"""Transactions CRUD. Income transactions can be allocated afterwards."""

from datetime import date
date_type = date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Transaction
from app.serializers import transaction_dict
from app.services.allocation import get_unallocated_for_tx

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

_SORT_COLUMNS = {"date": Transaction.date, "amount": Transaction.amount}


class TransactionBody(BaseModel):
    type: str  # income | expense | transfer
    amount: Decimal
    date: date_type | None = None
    category_id: int | None = None
    user_id: int | None = None
    comment: str | None = None


@router.get("")
def list_transactions(
    year: int | None = None,
    month: int | None = None,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    type: str | None = None,
    category_id: int | None = None,
    user_id: int | None = None,
    sort_by: str = "date",
    sort_dir: str = "desc",
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Transaction)
    if year:
        q = q.filter(extract("year", Transaction.date) == year)
    if month:
        q = q.filter(extract("month", Transaction.date) == month)
    if date_from:
        q = q.filter(Transaction.date >= date_from)
    if date_to:
        q = q.filter(Transaction.date <= date_to)
    if type:
        q = q.filter(Transaction.type == type)
    if category_id:
        q = q.filter(Transaction.category_id == category_id)
    if user_id:
        q = q.filter(Transaction.user_id == user_id)

    total = q.count()

    column = _SORT_COLUMNS.get(sort_by, Transaction.date)
    order = column.asc() if sort_dir == "asc" else column.desc()
    rows = (
        q.order_by(order, Transaction.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {"items": [transaction_dict(t) for t in rows], "total": total}


@router.post("")
def create_transaction(body: TransactionBody, db: Session = Depends(get_db)):
    tx = Transaction(
        type=body.type,
        amount=body.amount,
        date=body.date or date.today(),
        category_id=body.category_id,
        user_id=body.user_id,
        comment=body.comment,
    )
    db.add(tx)
    db.flush()
    db.commit()
    db.refresh(tx)
    result = transaction_dict(tx)
    if tx.type == "income":
        result["unallocated"] = float(get_unallocated_for_tx(db, tx))
    return result


@router.patch("/{tx_id}")
def update_transaction(tx_id: int, body: TransactionBody, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(404, "transaction not found")
    tx.type = body.type
    tx.amount = body.amount
    if body.date:
        tx.date = body.date
    tx.category_id = body.category_id
    tx.user_id = body.user_id
    tx.comment = body.comment
    db.commit()
    db.refresh(tx)
    return transaction_dict(tx)


@router.delete("/{tx_id}")
def delete_transaction(tx_id: int, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        return {"ok": True}
    db.delete(tx)
    db.commit()
    return {"ok": True}
