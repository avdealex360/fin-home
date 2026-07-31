"""Analytics bundle: plan vs fact, trends, pair breakdown."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import ws_id, ym_params
from app.db import get_db
from app.services.analytics import AnalyticsService
from app.services.pair_analytics import PairAnalyticsService
from app.util import period_date_range

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("")
def analytics(
    period: str = "month",
    ym: tuple[int, int] = Depends(ym_params),
    db: Session = Depends(get_db),
    ws: int = Depends(ws_id),
):
    year, month = ym
    start, end = period_date_range(year, month, period)
    top = AnalyticsService.top_categories(db, ws, start, end)
    return {
        "period": period,
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "plan_vs_fact": AnalyticsService.plan_vs_fact(db, ws, start, end),
        "top_categories": [{"name": n, "amount": float(a)} for n, a in top],
        "monthly_trends": AnalyticsService.monthly_trends(db, ws, 12, anchor=(year, month)),
        "cumulative_trends": AnalyticsService.cumulative_trends(db, ws, 12, anchor=(year, month)),
        "pair": PairAnalyticsService.monthly_breakdown(db, ws, start, end),
        "split_503020": AnalyticsService.split_503020(db, ws, start, end),
    }
