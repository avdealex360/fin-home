from __future__ import annotations
"""Deposit: settings + compound-interest forecast calculator."""

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
    # NOTE: balance is intentionally excluded — balance is grow-only and must
    # only change via POST /api/deposit/contribute or DepositService.rollback_for_income.
    rate: Decimal | None = None
    cap_day: int | None = None
    start_date: date_type | None = None
    monthly_target: Decimal | None = None
    initial_lump: Decimal | None = None
    rate_schedule: str | None = None  # raw JSON string


class ContributeBody(BaseModel):
    amount: Decimal
    date: date_type | None = None
    note: str | None = None


def _settings_response(db: Session) -> dict:
    s = DepositService.get_settings(db)
    return {
        "balance": float(s["balance"]),
        "rate": float(s["rate"]),
        "cap_day": s["cap_day"],
        "start_date": s["start_date"].isoformat() if s["start_date"] else None,
        "monthly_target": float(s["monthly_target"]),
        "initial_lump": float(Decimal(get_setting(db, "deposit_initial_lump", "0") or "0")),
        "rate_schedule": get_setting(db, "deposit_rate_schedule", "[]"),
    }


@router.get("")
def get_deposit(db: Session = Depends(get_db)):
    return _settings_response(db)


@router.post("")
def update_deposit(body: DepositSettingsBody, db: Session = Depends(get_db)):
    if body.rate is not None:
        set_setting(db, "deposit_rate", str(body.rate))
    if body.cap_day is not None:
        set_setting(db, "deposit_cap_day", str(body.cap_day))
    if body.start_date is not None:
        set_setting(db, "deposit_start_date", body.start_date.isoformat())
    if body.monthly_target is not None:
        set_setting(db, "deposit_monthly_target", str(body.monthly_target))
    if body.initial_lump is not None:
        set_setting(db, "deposit_initial_lump", str(body.initial_lump))
    if body.rate_schedule is not None:
        set_setting(db, "deposit_rate_schedule", body.rate_schedule)
    return _settings_response(db)


@router.post("/contribute")
def contribute(body: ContributeBody, db: Session = Depends(get_db)):
    DepositService.contribute(db, body.amount, body.date, "manual", body.note)
    return _settings_response(db)


@router.get("/calculator")
def calculator(
    monthly: Decimal,
    target_date: date_type,
    db: Session = Depends(get_db),
):
    rows = DepositService.forecast_detailed(db, monthly, target_date)
    return {
        "rows": [
            {
                "date": r.date.isoformat(),
                "balance_after": float(r.balance_after),
                "interest": float(getattr(r, "interest", 0) or 0),
                "contribution": float(getattr(r, "contribution", 0) or 0),
            }
            for r in rows
        ],
        "final_balance": float(rows[-1].balance_after) if rows else 0.0,
    }
