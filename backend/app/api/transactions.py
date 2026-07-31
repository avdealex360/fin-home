from __future__ import annotations
"""Transactions CRUD."""

from datetime import date
date_type = date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.api.deps import ws_id
from app.db import get_db
from app.models import Category, Transaction
from app.serializers import transaction_dict

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
    category_ids: list[int] | None = Query(None),
    group: str | None = None,
    user_id: int | None = None,
    sort_by: str = "date",
    sort_dir: str = "desc",
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    ws: int = Depends(ws_id),
):
    q = db.query(Transaction).filter(Transaction.workspace_id == ws)
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
    if category_ids:
        q = q.filter(Transaction.category_id.in_(category_ids))
    elif category_id:
        q = q.filter(Transaction.category_id == category_id)
    if group:
        q = q.join(Category, Transaction.category_id == Category.id).filter(Category.group == group)
    if user_id:
        q = q.filter(Transaction.user_id == user_id)

    total = q.count()

    # Expense totals per day/month over the FULL filtered set (not just this page),
    # so a header total stays correct even when its group spans multiple pages.
    expense_q = q.filter(Transaction.type == "expense")
    day_totals = {
        d.isoformat(): float(s)
        for d, s in expense_q.with_entities(Transaction.date, func.sum(Transaction.amount))
        .group_by(Transaction.date)
        .all()
    }
    month_totals = {
        f"{int(y)}-{int(m):02d}": float(s)
        for y, m, s in expense_q.with_entities(
            extract("year", Transaction.date), extract("month", Transaction.date), func.sum(Transaction.amount)
        )
        .group_by(extract("year", Transaction.date), extract("month", Transaction.date))
        .all()
    }

    column = _SORT_COLUMNS.get(sort_by, Transaction.date)
    order = column.asc() if sort_dir == "asc" else column.desc()
    rows = (
        q.order_by(order, Transaction.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "items": [transaction_dict(t) for t in rows],
        "total": total,
        "day_totals": day_totals,
        "month_totals": month_totals,
    }


@router.post("")
def create_transaction(body: TransactionBody, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    tx = Transaction(
        workspace_id=ws,
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
    return transaction_dict(tx)


@router.patch("/{tx_id}")
def update_transaction(
    tx_id: int, body: TransactionBody, db: Session = Depends(get_db), ws: int = Depends(ws_id)
):
    tx = (
        db.query(Transaction)
        .filter(Transaction.id == tx_id, Transaction.workspace_id == ws)
        .first()
    )
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
def delete_transaction(tx_id: int, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    tx = (
        db.query(Transaction)
        .filter(Transaction.id == tx_id, Transaction.workspace_id == ws)
        .first()
    )
    if not tx:
        return {"ok": True}
    db.delete(tx)
    db.commit()
    return {"ok": True}
