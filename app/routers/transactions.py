from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, Transaction
from app.templates_config import templates

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/new", response_class=HTMLResponse)
def new_transaction_form(request: Request, db: Session = Depends(get_db)):
    from app.models import AppUser

    categories = db.query(Category).filter(Category.is_hidden.is_(False)).order_by(Category.sort_order).all()
    users = db.query(AppUser).filter(AppUser.is_active.is_(True)).all()
    return templates.TemplateResponse(
        request,
        "transaction_form.html",
        {"categories": categories, "users": users, "today": date.today().isoformat(), "transaction": None},
    )


@router.post("/")
def create_transaction(
    request: Request,
    type: str = Form(...),
    amount: str = Form(...),
    date_str: str = Form(..., alias="date"),
    category_id: str = Form(""),
    user_id: str = Form(""),
    comment: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        amt = Decimal(amount.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return RedirectResponse("/transactions/new?error=amount", status_code=303)

    tx = Transaction(
        type=type,
        amount=amt,
        date=date.fromisoformat(date_str),
        category_id=int(category_id) if category_id else None,
        user_id=int(user_id) if user_id else None,
        comment=comment or None,
    )
    db.add(tx)
    db.commit()

    if request.headers.get("HX-Request"):
        return _recent_partial(request, db)
    return RedirectResponse("/", status_code=303)


@router.post("/quick")
def quick_transaction(
    request: Request,
    type: str = Form(...),
    amount: str = Form(...),
    date_str: str = Form(..., alias="date"),
    category_id: str = Form(""),
    user_id: str = Form(""),
    comment: str = Form(""),
    db: Session = Depends(get_db),
):
    return create_transaction(request, type, amount, date_str, category_id, user_id, comment, db)


@router.get("/recent/partial", response_class=HTMLResponse)
def recent_partial(request: Request, db: Session = Depends(get_db)):
    return _recent_partial(request, db)


@router.get("/{tx_id}/edit", response_class=HTMLResponse)
def edit_transaction(request: Request, tx_id: int, db: Session = Depends(get_db)):
    from app.models import AppUser

    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        return RedirectResponse("/", status_code=303)
    categories = db.query(Category).filter(Category.is_hidden.is_(False)).order_by(Category.sort_order).all()
    users = db.query(AppUser).filter(AppUser.is_active.is_(True)).all()
    return templates.TemplateResponse(
        request,
        "transaction_form.html",
        {
            "categories": categories,
            "users": users,
            "today": date.today().isoformat(),
            "transaction": tx,
        },
    )


@router.post("/{tx_id}")
def update_transaction(
    request: Request,
    tx_id: int,
    type: str = Form(...),
    amount: str = Form(...),
    date_str: str = Form(..., alias="date"),
    category_id: str = Form(""),
    user_id: str = Form(""),
    comment: str = Form(""),
    db: Session = Depends(get_db),
):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        return RedirectResponse("/", status_code=303)
    tx.type = type
    tx.amount = Decimal(amount.replace(",", ".").replace(" ", ""))
    tx.date = date.fromisoformat(date_str)
    tx.category_id = int(category_id) if category_id else None
    tx.user_id = int(user_id) if user_id else None
    tx.comment = comment or None
    db.commit()
    return RedirectResponse("/", status_code=303)


@router.delete("/{tx_id}")
def delete_transaction(request: Request, tx_id: int, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if tx:
        db.delete(tx)
        db.commit()
    if request.headers.get("HX-Request"):
        return _recent_partial(request, db)
    return RedirectResponse("/", status_code=303)


def _recent_partial(request: Request, db: Session) -> HTMLResponse:
    recent = (
        db.query(Transaction)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(10)
        .all()
    )
    return templates.TemplateResponse(request, "partials/recent_transactions.html", {"recent": recent})
