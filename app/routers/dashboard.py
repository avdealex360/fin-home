from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.dashboard import DashboardService
from app.services.rules import RuleEngine
from app.templates_config import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    from datetime import date

    today = date.today()
    summary = DashboardService.get_month_summary(db, today.year, today.month)
    advice_tiers = RuleEngine.evaluate(db, today.year, today.month)
    RuleEngine.mark_shown(db, advice_tiers)

    from app.models import AppUser, Category, SinkingFund, Transaction

    recent = (
        db.query(Transaction)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(10)
        .all()
    )
    categories = (
        db.query(Category)
        .filter(Category.is_hidden.is_(False))
        .order_by(Category.sort_order)
        .all()
    )
    expense_categories = [c for c in categories if c.group != "income"]
    income_categories = [c for c in categories if c.group == "income"]
    users = db.query(AppUser).filter(AppUser.is_active.is_(True)).all()
    funds = db.query(SinkingFund).filter(SinkingFund.is_active.is_(True)).all()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "summary": summary,
            "advice_tiers": advice_tiers,
            "recent": recent,
            "categories": expense_categories,
            "income_categories": income_categories,
            "all_categories": categories,
            "users": users,
            "funds": funds,
            "today": today.isoformat(),
        },
    )
