from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, Transaction
from app.services.exchange import eur_to_rub, get_eur_rub_rate
from app.services.goals import remove_goal_from_transaction, sync_goal_from_transaction
from app.templates_config import templates

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _parse_amount(value: str) -> Decimal:
    return Decimal(value.replace(",", ".").replace(" ", ""))


@router.get("/new")
def new_transaction_redirect():
    return RedirectResponse("/", status_code=303)


def _create_tx(
    db: Session,
    type: str,
    amount: str,
    date_str: str,
    category_id: str,
    user_id: str,
    comment: str,
    base_amount_eur: str = "",
    fund_id: str = "",
    is_sinking_spend: bool = False,
) -> Transaction | None:
    try:
        amt = _parse_amount(amount)
    except InvalidOperation:
        return None

    eur = None
    exchange_rate = None
    if type == "income" and base_amount_eur:
        try:
            eur = _parse_amount(base_amount_eur)
            rate = get_eur_rub_rate(db)
            exchange_rate = rate
            amt = eur_to_rub(eur, rate)
        except InvalidOperation:
            eur = None

    if is_sinking_spend and fund_id:
        from app.services.sinking_funds import SinkingFundService

        return SinkingFundService.spend_from_fund(
            db,
            int(fund_id),
            amt,
            date.fromisoformat(date_str),
            int(category_id) if category_id else None,
            int(user_id) if user_id else None,
            comment or None,
        )

    tx = Transaction(
        type=type,
        amount=amt,
        date=date.fromisoformat(date_str),
        category_id=int(category_id) if category_id else None,
        user_id=int(user_id) if user_id else None,
        comment=comment or None,
        base_amount_eur=eur if type == "income" else None,
        exchange_rate=exchange_rate,
        is_fully_allocated=False if type == "income" else False,
        is_sinking_fund_spend=is_sinking_spend,
        fund_id=int(fund_id) if fund_id else None,
    )
    db.add(tx)
    db.flush()
    if type in ("expense", "transfer"):
        sync_goal_from_transaction(db, tx)
    db.commit()
    return tx


@router.post("/")
def create_transaction(
    request: Request,
    type: str = Form(...),
    amount: str = Form(...),
    date_str: str = Form(..., alias="date"),
    category_id: str = Form(""),
    user_id: str = Form(""),
    comment: str = Form(""),
    base_amount_eur: str = Form(""),
    fund_id: str = Form(""),
    db: Session = Depends(get_db),
):
    is_sinking = bool(fund_id)
    tx = _create_tx(
        db, type, amount, date_str, category_id, user_id, comment, base_amount_eur, fund_id, is_sinking
    )
    if not tx:
        return RedirectResponse("/?error=amount", status_code=303)

    if request.headers.get("HX-Request"):
        return _recent_partial(request, db)
    if type == "income":
        return RedirectResponse(f"/allocate/{tx.id}", status_code=303)
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
    base_amount_eur: str = Form(""),
    fund_id: str = Form(""),
    db: Session = Depends(get_db),
):
    return create_transaction(
        request, type, amount, date_str, category_id, user_id, comment, base_amount_eur, fund_id, db
    )


@router.get("/recent/partial", response_class=HTMLResponse)
def recent_partial(request: Request, db: Session = Depends(get_db)):
    return _recent_partial(request, db)


@router.get("/{tx_id}/edit", response_class=HTMLResponse)
def edit_transaction(request: Request, tx_id: int, db: Session = Depends(get_db)):
    from app.models import AppUser, SinkingFund

    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        return RedirectResponse("/", status_code=303)
    expense_cats = (
        db.query(Category)
        .filter(Category.is_hidden.is_(False), Category.group.in_(["needs", "wants", "savings"]))
        .order_by(Category.sort_order)
        .all()
    )
    income_cats = (
        db.query(Category)
        .filter(Category.is_hidden.is_(False), Category.group == "income")
        .order_by(Category.sort_order)
        .all()
    )
    users = db.query(AppUser).filter(AppUser.is_active.is_(True)).all()
    funds = db.query(SinkingFund).filter(SinkingFund.is_active.is_(True)).all()
    return templates.TemplateResponse(
        request,
        "transaction_form.html",
        {
            "categories": expense_cats,
            "income_categories": income_cats,
            "all_categories": expense_cats + income_cats,
            "users": users,
            "funds": funds,
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
    base_amount_eur: str = Form(""),
    db: Session = Depends(get_db),
):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        return RedirectResponse("/", status_code=303)
    remove_goal_from_transaction(db, tx)
    tx.type = type
    tx.amount = _parse_amount(amount)
    tx.date = date.fromisoformat(date_str)
    tx.category_id = int(category_id) if category_id else None
    tx.user_id = int(user_id) if user_id else None
    tx.comment = comment or None
    if type == "income" and base_amount_eur:
        try:
            eur = _parse_amount(base_amount_eur)
            rate = get_eur_rub_rate(db)
            tx.base_amount_eur = eur
            tx.exchange_rate = rate
            tx.amount = eur_to_rub(eur, rate)
        except InvalidOperation:
            tx.base_amount_eur = None
            tx.exchange_rate = None
    else:
        tx.base_amount_eur = None
        tx.exchange_rate = None
    sync_goal_from_transaction(db, tx)
    db.commit()
    return RedirectResponse("/", status_code=303)


@router.delete("/{tx_id}")
def delete_transaction(request: Request, tx_id: int, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if tx:
        remove_goal_from_transaction(db, tx)
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
