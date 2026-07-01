from __future__ import annotations
"""Deposit: a standalone compound-interest calculator. Purely informational —
it never touches transactions, categories, or the 50/30/20 budget."""

from datetime import date as date_type
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.deposit import DepositService
from app.services.settings_store import get_setting, set_setting

router = APIRouter(prefix="/api/deposit", tags=["deposit"])


class DepositSettingsBody(BaseModel):
    rate: Decimal | None = None
    start_date: date_type | None = None
    term_months: int | None = None
    initial_lump: Decimal | None = None
    monthly_contribution: Decimal | None = None
    rate_schedule: str | None = None  # raw JSON string: [{"from": "YYYY-MM-DD", "rate": 17.5}, ...]


def _settings_response(db: Session) -> dict:
    s = DepositService.get_settings(db)
    return {
        "rate": float(s["rate"]),
        "start_date": s["start_date"].isoformat() if s["start_date"] else None,
        "term_months": s["term_months"],
        "initial_lump": float(s["initial_lump"]),
        "monthly_contribution": float(s["monthly_contribution"]),
        "rate_schedule": get_setting(db, "deposit_rate_schedule", "[]"),
    }


@router.get("")
def get_deposit(db: Session = Depends(get_db)):
    return _settings_response(db)


@router.post("")
def update_deposit(body: DepositSettingsBody, db: Session = Depends(get_db)):
    if body.rate is not None:
        set_setting(db, "deposit_rate", str(body.rate))
    if body.start_date is not None:
        set_setting(db, "deposit_start_date", body.start_date.isoformat())
    if body.term_months is not None:
        set_setting(db, "deposit_term_months", str(body.term_months))
    if body.initial_lump is not None:
        set_setting(db, "deposit_initial_lump", str(body.initial_lump))
    if body.monthly_contribution is not None:
        set_setting(db, "deposit_monthly_target", str(body.monthly_contribution))
    if body.rate_schedule is not None:
        set_setting(db, "deposit_rate_schedule", body.rate_schedule)
    return _settings_response(db)


@router.get("/calculator")
def calculator(monthly: Decimal | None = None, db: Session = Depends(get_db)):
    rows = DepositService.forecast(db, monthly)
    return {
        "rows": [
            {
                "date": r.date.isoformat(),
                "balance_after": float(r.balance_after),
                "interest": float(r.interest),
                "contribution": float(r.contribution),
            }
            for r in rows
        ],
        "final_balance": float(rows[-1].balance_after) if rows else 0.0,
    }
