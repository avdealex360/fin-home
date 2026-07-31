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
    total = AnalyticsService.expense_total(db, ws, start, end)
    top_sum = sum((a for _, a in top), start=total * 0)
    top_categories = [{"name": n, "amount": float(a)} for n, a in top]
    # The donut shows shares of ALL spend, so the tail outside the top 5
    # becomes an explicit "Прочее" slice instead of silently vanishing.
    if total - top_sum > 0:
        top_categories.append({"name": "Прочее", "amount": float(total - top_sum)})
    return {
        "period": period,
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "plan_vs_fact": AnalyticsService.plan_vs_fact(db, ws, start, end),
        "top_categories": top_categories,
        "expense_total": float(total),
        "monthly_trends": AnalyticsService.monthly_trends(db, ws, 12, anchor=(year, month)),
        "pair": PairAnalyticsService.monthly_breakdown(db, ws, start, end),
    }
