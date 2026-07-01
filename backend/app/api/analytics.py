"""Analytics bundle: plan vs fact, trends, forecasts, pair breakdown."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import ym_params
from app.db import get_db
from app.services.analytics import AnalyticsService
from app.services.forecast import ForecastService
from app.services.pair_analytics import PairAnalyticsService
from app.util import period_date_range

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("")
def analytics(
    period: str = "month",
    ym: tuple[int, int] = Depends(ym_params),
    db: Session = Depends(get_db),
):
    year, month = ym
    start, end = period_date_range(year, month, period)
    top = AnalyticsService.top_categories(db, start, end)
    return {
        "period": period,
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "plan_vs_fact": AnalyticsService.plan_vs_fact(db, start, end),
        "top_categories": [{"name": n, "amount": float(a)} for n, a in top],
        "monthly_trends": AnalyticsService.monthly_trends(db, 12, anchor=(year, month)),
        "cumulative_trends": AnalyticsService.cumulative_trends(db, 12, anchor=(year, month)),
        "cash_flow": ForecastService.cash_flow_forecast(db, 3),
        "pair": PairAnalyticsService.monthly_breakdown(db, start, end),
        "split_503020": AnalyticsService.split_503020(db, start, end),
    }


@router.get("/category/{category_id}")
def category_history(category_id: int, months: int = 6, db: Session = Depends(get_db)):
    history = AnalyticsService.category_history(db, category_id, months)
    return {
        "history": [{"year": y, "month": m, "amount": float(a)} for y, m, a in history],
        "average": float(AnalyticsService.category_average(db, category_id, months)),
    }
