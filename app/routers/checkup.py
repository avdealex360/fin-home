from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Debt, Goal, SinkingFund
from app.services.settings_store import get_setting
from app.services.debts import debt_cost_analysis
from app.services.forecast import ForecastService
from app.services.goals import cascade_goal_scenario
from app.services.plan import DepositService
from app.templates_config import templates

router = APIRouter(prefix="/checkup", tags=["checkup"])


@router.get("/", response_class=HTMLResponse)
def checkup_page(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    funds = db.query(SinkingFund).filter(SinkingFund.is_active.is_(True)).all()
    goals = db.query(Goal).filter(Goal.is_active.is_(True)).all()
    debts = db.query(Debt).filter(Debt.is_closed.is_(False)).all()
    deposit = DepositService.get_settings(db)

    split = db.query(Debt).filter(Debt.name == "Яндекс Сплит").first()
    pillow = db.query(Goal).filter(Goal.name == "Подушка безопасности").first()
    cascade = None
    if split and pillow and not split.is_closed:
        cascade = cascade_goal_scenario(db, pillow, split.monthly_payment)

    debt_costs = [debt_cost_analysis(db, d.id) for d in debts]

    return templates.TemplateResponse(
        request,
        "checkup.html",
        {
            "today": today,
            "funds": funds,
            "goals": goals,
            "debts": debts,
            "deposit_rate": deposit["rate"],
            "eur_rub_rate": get_setting(db, "eur_rub_rate", "100"),
            "cascade": cascade,
            "debt_costs": [c for c in debt_costs if c],
        },
    )
