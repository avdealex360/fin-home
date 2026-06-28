import csv
import io
import json
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, Debt, Goal, Setting, Transaction
from app.services.settings_store import set_setting
from app.templates_config import templates

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    categories = db.query(Category).order_by(Category.sort_order).all()
    debts = db.query(Debt).order_by(Debt.id).all()
    goals = db.query(Goal).filter(Goal.is_active.is_(True)).all()
    settings = {s.key: s.value for s in db.query(Setting).all()}
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"categories": categories, "debts": debts, "goals": goals, "settings": settings},
    )


@router.post("/general")
def save_general(
    user1_name: str = Form(...),
    user2_name: str = Form(...),
    currency: str = Form("RUB"),
    eur_usd_rate: str = Form("1.08"),
    eur_rub_rate: str = Form("100"),
    db: Session = Depends(get_db),
):
    set_setting(db, "user1_name", user1_name)
    set_setting(db, "user2_name", user2_name)
    set_setting(db, "currency", currency)
    set_setting(db, "eur_usd_rate", eur_usd_rate)
    set_setting(db, "eur_rub_rate", eur_rub_rate)

    from app.models import AppUser

    users = db.query(AppUser).order_by(AppUser.id).all()
    if len(users) >= 1:
        users[0].name = user1_name
    if len(users) >= 2:
        users[1].name = user2_name
    db.commit()
    return RedirectResponse("/settings?saved=1", status_code=303)


@router.post("/password")
def change_password(
    new_password: str = Form(...),
):
    # Note: password is in .env, show message to update manually
    return RedirectResponse("/settings?password_hint=1", status_code=303)


@router.post("/categories")
def add_category(
    name: str = Form(...),
    group: str = Form(...),
    db: Session = Depends(get_db),
):
    max_order = db.query(Category).count()
    db.add(Category(name=name, group=group, sort_order=max_order + 1))
    db.commit()
    return RedirectResponse("/settings?saved=1", status_code=303)


@router.post("/categories/{cat_id}/toggle")
def toggle_category(cat_id: int, db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if cat:
        cat.is_hidden = not cat.is_hidden
        db.commit()
    return RedirectResponse("/settings", status_code=303)


@router.post("/debts")
def add_debt(
    name: str = Form(...),
    total_amount: str = Form(...),
    remaining: str = Form(...),
    monthly_payment: str = Form("0"),
    interest_rate: str = Form("0"),
    type: str = Form(...),
    grace_period_end: str = Form(""),
    db: Session = Depends(get_db),
):
    debt = Debt(
        name=name,
        total_amount=Decimal(total_amount.replace(",", ".").replace(" ", "")),
        remaining=Decimal(remaining.replace(",", ".").replace(" ", "")),
        monthly_payment=Decimal(monthly_payment.replace(",", ".").replace(" ", "")),
        interest_rate=Decimal(interest_rate.replace(",", ".").replace(" ", "")),
        type=type,
        grace_period_end=date.fromisoformat(grace_period_end) if grace_period_end else None,
        start_date=date.today(),
    )
    db.add(debt)
    db.commit()
    return RedirectResponse("/settings?saved=1", status_code=303)


@router.post("/debts/{debt_id}/close")
def close_debt(debt_id: int, db: Session = Depends(get_db)):
    debt = db.query(Debt).filter(Debt.id == debt_id).first()
    if debt:
        debt.is_closed = True
        debt.remaining = Decimal("0")
        db.commit()
    return RedirectResponse("/settings", status_code=303)


@router.post("/debts/{debt_id}/payment")
def record_debt_payment(
    debt_id: int,
    amount: str = Form(...),
    date_str: str = Form(..., alias="date"),
    comment: str = Form(""),
    db: Session = Depends(get_db),
):
    from app.models import DebtPayment

    debt = db.query(Debt).filter(Debt.id == debt_id).first()
    if not debt:
        return RedirectResponse("/settings", status_code=303)
    try:
        amt = Decimal(amount.replace(",", ".").replace(" ", ""))
    except Exception:
        return RedirectResponse("/settings?error=1", status_code=303)

    db.add(
        DebtPayment(
            debt_id=debt_id,
            amount=amt,
            date=date.fromisoformat(date_str),
            comment=comment or None,
        )
    )
    debt.remaining = max(Decimal("0"), debt.remaining - amt)
    if debt.remaining <= 0:
        debt.is_closed = True
    db.commit()
    return RedirectResponse("/settings?saved=1", status_code=303)


@router.post("/fetch-eur-rate")
async def fetch_eur_rate(db: Session = Depends(get_db)):
    from app.services.exchange import fetch_eur_usd_rate, update_eur_usd_rate

    await update_eur_usd_rate(db)
    return RedirectResponse("/settings?rate_updated=1", status_code=303)


@router.get("/export/json")
def export_json(db: Session = Depends(get_db)):
    data = {
        "transactions": [
            {
                "id": t.id,
                "type": t.type,
                "amount": str(t.amount),
                "date": t.date.isoformat(),
                "category_id": t.category_id,
                "comment": t.comment,
                "base_amount_eur": str(t.base_amount_eur) if t.base_amount_eur else None,
            }
            for t in db.query(Transaction).all()
        ],
        "categories": [
            {"id": c.id, "name": c.name, "group": c.group}
            for c in db.query(Category).all()
        ],
        "debts": [
            {"id": d.id, "name": d.name, "remaining": str(d.remaining)}
            for d in db.query(Debt).all()
        ],
        "goals": [
            {"id": g.id, "name": g.name, "current_amount": str(g.current_amount)}
            for g in db.query(Goal).all()
        ],
        "settings": {s.key: s.value for s in db.query(Setting).all()},
    }
    content = json.dumps(data, ensure_ascii=False, indent=2)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=budget_export.json"},
    )


@router.get("/export/csv")
def export_csv(db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "type", "amount", "date", "category", "comment", "base_amount_eur"])
    for t in db.query(Transaction).order_by(Transaction.date).all():
        cat_name = t.category.name if t.category else ""
        writer.writerow([
            t.id, t.type, str(t.amount), t.date.isoformat(), cat_name,
            t.comment or "", str(t.base_amount_eur) if t.base_amount_eur else "",
        ])
    content = output.getvalue()
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )
