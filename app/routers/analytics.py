from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, Debt
from app.services.analytics import AnalyticsService
from app.services.debts import debt_cost_analysis
from app.services.forecast import ForecastService
from app.services.pair_analytics import PairAnalyticsService
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
                "cost": debt_cost_analysis(db, debt.id),
            }
        )

    cat_history = []
    cat_average = None
    if category_id:
        cat_history = AnalyticsService.category_history(db, category_id, 6)
        cat_average = AnalyticsService.category_average(db, category_id, 6)

    cumulative = AnalyticsService.cumulative_trends(db, 12)
    chart_labels = [f"{t.year}-{t.month:02d}" for t in trends]
    chart_income = [float(t.income) for t in trends]
    chart_expense = [float(t.expense) for t in trends]
    chart_savings = [float(t.savings) for t in trends]
    cum_labels = [c["label"] for c in cumulative]
    cum_income = [c["income"] for c in cumulative]
    cum_expense = [c["expense"] for c in cumulative]
    cum_savings = [c["savings"] for c in cumulative]
    cat_chart_labels = [f"{y}-{m:02d}" for y, m, _ in cat_history]
    cat_chart_values = [float(v) for _, _, v in cat_history]

    cash_flow = ForecastService.cash_flow_forecast(db, 3)
    cascade = ForecastService.cascade_after_debt_close(db)
    pair = PairAnalyticsService.monthly_breakdown(db, year, month)

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
            "cat_average": cat_average,
            "debts": debt_data,
            "chart_labels": chart_labels,
            "chart_income": chart_income,
            "chart_expense": chart_expense,
            "chart_savings": chart_savings,
            "cum_labels": cum_labels,
            "cum_income": cum_income,
            "cum_expense": cum_expense,
            "cum_savings": cum_savings,
            "cat_chart_labels": cat_chart_labels,
            "cat_chart_values": cat_chart_values,
            "cash_flow": cash_flow,
            "cascade": cascade,
            "pair": pair,
        },
    )
