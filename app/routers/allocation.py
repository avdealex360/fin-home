from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Transaction
from app.services.allocation import (
    AllocationInput,
    allocate_income,
    get_allocation_levels,
    get_unallocated_for_tx,
)
from app.templates_config import templates

router = APIRouter(tags=["allocation"])


def _parse_amount(value: str) -> Decimal:
    return Decimal(value.replace(",", ".").replace(" ", ""))


@router.get("/allocate/{tx_id}", response_class=HTMLResponse)
def allocate_page(request: Request, tx_id: int, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx or tx.type != "income":
        return RedirectResponse("/", status_code=303)

    levels = get_allocation_levels(db, tx.date.year, tx.date.month, tx.amount)
    unallocated = get_unallocated_for_tx(db, tx)

    return templates.TemplateResponse(
        request,
        "allocate.html",
        {
            "tx": tx,
            "levels": levels,
            "unallocated": unallocated,
            "income_amount": tx.amount,
        },
    )


@router.post("/allocate/{tx_id}")
async def allocate_submit(request: Request, tx_id: int, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx or tx.type != "income":
        return RedirectResponse("/", status_code=303)

    form = await request.form()
    allocations: list[AllocationInput] = []

    for key, value in form.items():
        if not value:
            continue
        try:
            amount = _parse_amount(str(value))
        except InvalidOperation:
            continue
        if amount <= 0:
            continue
        if key.startswith("cat_"):
            parts = key.split("_")
            level = int(parts[2]) if len(parts) > 2 else 4
            cat_id = int(parts[1])
            allocations.append(
                AllocationInput(category_id=cat_id, amount=amount, allocation_level=level)
            )
        elif key.startswith("fund_"):
            fund_id = int(key.replace("fund_", ""))
            allocations.append(
                AllocationInput(fund_id=fund_id, amount=amount, allocation_level=3)
            )

    try:
        allocate_income(db, tx_id, allocations)
    except ValueError:
        return RedirectResponse(f"/allocate/{tx_id}?error=1", status_code=303)

    return RedirectResponse("/?allocated=1", status_code=303)


@router.get("/allocate/{tx_id}/preview", response_class=HTMLResponse)
def allocate_preview(request: Request, tx_id: int, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        return HTMLResponse("")
    levels = get_allocation_levels(db, tx.date.year, tx.date.month, tx.amount)
    remainder = tx.amount
    lines = []
    for level in levels:
        remainder -= level.total_suggested
        lines.append(f"После L{level.level}: {remainder:,.0f} ₽".replace(",", " "))
    return HTMLResponse("<br>".join(lines))
