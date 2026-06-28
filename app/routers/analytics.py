from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, Debt
from app.services.analytics import AnalyticsService
from app.templates_config import templates

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/", response_class=HTMLResponse)
def analytics_page(
    request: Request,
    year: int | None = None,
    month: int | None = None,
    category_id: int | None = None,
    db: Session = Depends(get_db),
):
    today = date.today()
    year = year or today.year
    month = month or today.month

    comparison = AnalyticsService.plan_vs_fact(db, year, month)
    trends = AnalyticsService.monthly_trends(db, 12)
    top = AnalyticsService.top_categories(db, year, month)
    categories = db.query(Category).filter(Category.is_hidden.is_(False)).order_by(Category.sort_order).all()
    debts = db.query(Debt).order_by(Debt.id).all()
    debt_data = []
    for debt in debts:
        debt_data.append(
            {
                "debt": debt,
                "forecast": AnalyticsService.debt_forecast(db, debt.id),
                "payments": AnalyticsService.debt_payments(db, debt.id),
            }
        )

    cat_history = []
    if category_id:
        cat_history = AnalyticsService.category_history(db, category_id, 6)

    chart_labels = [f"{y}-{m:02d}" for y, m, _ in trends]
    chart_income = [float(t.income) for t in trends]
    chart_expense = [float(t.expense) for t in trends]
    chart_savings = [float(t.savings) for t in trends]
    cat_chart_labels = [f"{y}-{m:02d}" for y, m, _ in cat_history]
    cat_chart_values = [float(v) for _, _, v in cat_history]

    return templates.TemplateResponse(
        request,
        "analytics.html",
        {
            "year": year,
            "month": month,
            "comparison": comparison,
            "trends": trends,
            "top": top,
            "categories": categories,
            "category_id": category_id,
            "cat_history": cat_history,
            "debts": debt_data,
            "chart_labels": chart_labels,
            "chart_income": chart_income,
            "chart_expense": chart_expense,
            "chart_savings": chart_savings,
            "cat_chart_labels": cat_chart_labels,
            "cat_chart_values": cat_chart_values,
        },
    )
