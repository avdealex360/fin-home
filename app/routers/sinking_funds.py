from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, SinkingFund
from app.services.sinking_funds import SinkingFundService
from app.templates_config import templates

router = APIRouter(prefix="/funds", tags=["funds"])


@router.get("/", response_class=HTMLResponse)
def funds_page(request: Request, db: Session = Depends(get_db)):
    funds = SinkingFundService.list_active(db)
    categories = (
        db.query(Category)
        .filter(Category.is_hidden.is_(False), Category.group.in_(["needs", "wants"]))
        .order_by(Category.sort_order)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "funds.html",
        {"funds": funds, "categories": categories, "today": date.today().isoformat()},
    )


@router.post("/")
def create_fund(
    name: str = Form(...),
    target_amount: str = Form(...),
    monthly_contribution: str = Form(...),
    category_group: str = Form("needs"),
    target_date: str = Form(""),
    is_rolling: str = Form(""),
    linked_category_id: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        target = Decimal(target_amount.replace(",", ".").replace(" ", ""))
        monthly = Decimal(monthly_contribution.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return RedirectResponse("/funds?error=1", status_code=303)

    SinkingFundService.create(
        db,
        name=name,
        target_amount=target,
        monthly_contribution=monthly,
        category_group=category_group,
        target_date=date.fromisoformat(target_date) if target_date else None,
        is_rolling=bool(is_rolling),
        linked_category_id=int(linked_category_id) if linked_category_id else None,
    )
    return RedirectResponse("/funds?saved=1", status_code=303)


@router.post("/{fund_id}/contribute")
def contribute(
    fund_id: int,
    amount: str = Form(...),
    date_str: str = Form(..., alias="date"),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        amt = Decimal(amount.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return RedirectResponse("/funds?error=1", status_code=303)
    SinkingFundService.contribute(db, fund_id, amt, date.fromisoformat(date_str), note or None)
    return RedirectResponse("/funds?saved=1", status_code=303)


@router.post("/{fund_id}/spend")
def spend(
    fund_id: int,
    amount: str = Form(...),
    date_str: str = Form(..., alias="date"),
    comment: str = Form(""),
    user_id: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        amt = Decimal(amount.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return RedirectResponse("/funds?error=1", status_code=303)
    SinkingFundService.spend_from_fund(
        db,
        fund_id,
        amt,
        date.fromisoformat(date_str),
        None,
        int(user_id) if user_id else None,
        comment or None,
    )
    return RedirectResponse("/funds?saved=1", status_code=303)


@router.post("/{fund_id}/update")
def update_fund(
    fund_id: int,
    name: str = Form(...),
    target_amount: str = Form(...),
    monthly_contribution: str = Form(...),
    target_date: str = Form(""),
    is_rolling: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        target = Decimal(target_amount.replace(",", ".").replace(" ", ""))
        monthly = Decimal(monthly_contribution.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return RedirectResponse("/funds?error=1", status_code=303)
    SinkingFundService.update(
        db,
        fund_id,
        name,
        target,
        monthly,
        date.fromisoformat(target_date) if target_date else None,
        bool(is_rolling),
    )
    return RedirectResponse("/funds?saved=1", status_code=303)


@router.post("/{fund_id}/delete")
def delete_fund(fund_id: int, db: Session = Depends(get_db)):
    SinkingFundService.delete(db, fund_id)
    return RedirectResponse("/funds", status_code=303)
