from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.services.settings_store import get_setting


class DepositService:
    """A standalone compound-interest calculator — purely informational, it never
    touches transactions, categories, or the 50/30/20 budget."""

    @staticmethod
    def get_settings(db: Session) -> dict:
        from app.services.deposit_calc import parse_rate_schedule

        rate = Decimal(get_setting(db, "deposit_rate", "17.5") or "0")
        schedule_raw = get_setting(db, "deposit_rate_schedule", "")
        start_raw = get_setting(db, "deposit_start_date", "")
        return {
            "rate": rate,
            "cap_day": int(get_setting(db, "deposit_cap_day", "18") or "18"),
            "start_date": date.fromisoformat(start_raw) if start_raw else None,
            "rate_schedule": parse_rate_schedule(schedule_raw, rate),
            "term_months": int(get_setting(db, "deposit_term_months", "12") or "12"),
            "monthly_contribution": Decimal(get_setting(db, "deposit_monthly_target", "0") or "0"),
            "initial_lump": Decimal(get_setting(db, "deposit_initial_lump", "0") or "0"),
        }

    @staticmethod
    def forecast(db: Session, monthly_contribution: Decimal | None = None) -> list:
        from app.services.deposit_calc import add_months, build_forecast

        s = DepositService.get_settings(db)
        start = s["start_date"] or date.today()
        target_date = add_months(start, s["term_months"])
        monthly = monthly_contribution if monthly_contribution is not None else s["monthly_contribution"]
        return build_forecast(
            start,
            Decimal("0"),
            s["rate"],
            target_date,
            monthly,
            initial_lump_sum=s["initial_lump"],
            rate_schedule=s["rate_schedule"],
            capitalization_day=s["cap_day"],
        )
