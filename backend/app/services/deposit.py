from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import DepositContribution
from app.services.settings_store import get_setting, set_setting


class DepositService:
    @staticmethod
    def get_balance(db: Session) -> Decimal:
        return Decimal(get_setting(db, "deposit_balance", "0") or "0")

    @staticmethod
    def get_monthly_target(db: Session) -> Decimal:
        return Decimal(get_setting(db, "deposit_monthly_target", "0") or "0")

    @staticmethod
    def get_settings(db: Session) -> dict:
        from app.services.deposit_calc import parse_rate_schedule

        rate_raw = get_setting(db, "deposit_rate", "17.5")
        rate = Decimal(rate_raw or "0")
        schedule_raw = get_setting(db, "deposit_rate_schedule", "")
        return {
            "balance": DepositService.get_balance(db),
            "rate": rate,
            "cap_day": int(get_setting(db, "deposit_cap_day", "18") or "18"),
            "start_date": (
                date.fromisoformat(get_setting(db, "deposit_start_date", ""))
                if get_setting(db, "deposit_start_date", "") else None
            ),
            "rate_schedule": parse_rate_schedule(schedule_raw, rate),
            "monthly_target": DepositService.get_monthly_target(db),
        }

    @staticmethod
    def get_current(db: Session) -> tuple[Decimal, Decimal]:
        s = DepositService.get_settings(db)
        return s["balance"], s["rate"]

    @staticmethod
    def update(db: Session, balance: Decimal, rate: Decimal) -> None:
        set_setting(db, "deposit_balance", str(balance))
        set_setting(db, "deposit_rate", str(rate))

    @staticmethod
    def contribute(
        db: Session,
        amount: Decimal,
        on_date: date | None = None,
        source: str = "manual",
        note: str | None = None,
        income_tx_id: int | None = None,
    ) -> Decimal:
        if amount <= 0:
            raise ValueError("amount must be positive")
        db.add(DepositContribution(
            amount=amount,
            date=on_date or date.today(),
            source=source,
            note=note,
            income_tx_id=income_tx_id,
        ))
        new_balance = DepositService.get_balance(db) + amount
        set_setting(db, "deposit_balance", str(new_balance))
        db.commit()
        return new_balance

    @staticmethod
    def rollback_for_income(db: Session, income_tx_id: int) -> None:
        """Remove deposit contributions previously made from this income and lower the balance."""
        rows = (
            db.query(DepositContribution)
            .filter(DepositContribution.income_tx_id == income_tx_id)
            .all()
        )
        if not rows:
            return
        removed = sum((r.amount for r in rows), Decimal("0"))
        for r in rows:
            db.delete(r)
        new_balance = max(Decimal("0"), DepositService.get_balance(db) - removed)
        set_setting(db, "deposit_balance", str(new_balance))
        db.commit()

    @staticmethod
    def forecast(
        balance: Decimal,
        rate: Decimal,
        monthly_contribution: Decimal,
        target_date: date,
        start_date: date | None = None,
        rate_schedule: list | None = None,
        capitalization_day: int | None = None,
        initial_lump_sum: Decimal = Decimal("0"),
    ) -> list[tuple[date, Decimal]]:
        from app.services.deposit_calc import build_forecast

        start = start_date or date.today()
        rows = build_forecast(
            start,
            balance,
            rate,
            target_date,
            monthly_contribution,
            initial_lump_sum=initial_lump_sum,
            rate_schedule=rate_schedule,
            capitalization_day=capitalization_day,
        )
        return [(r.date, r.balance_after) for r in rows]

    @staticmethod
    def forecast_detailed(
        db: Session,
        monthly_contribution: Decimal,
        target_date: date,
    ) -> list:
        from app.services.deposit_calc import build_forecast

        s = DepositService.get_settings(db)
        start = s["start_date"] or date.today()
        initial_lump = Decimal(get_setting(db, "deposit_initial_lump", "0") or "0")
        # Таблица как в Excel: от даты открытия, стартовый остаток 0, разовый взнос в 1-й месяц
        return build_forecast(
            start,
            Decimal("0"),
            s["rate"],
            target_date,
            monthly_contribution,
            initial_lump_sum=initial_lump,
            rate_schedule=s["rate_schedule"],
            capitalization_day=s["cap_day"],
        )

    @staticmethod
    def forecast_forward(
        db: Session,
        monthly_contribution: Decimal,
        target_date: date,
    ) -> list:
        """Прогноз вперёд от текущего баланса (следующая дата капитализации)."""
        from app.services.deposit_calc import build_forecast, align_capitalization_day, add_months

        s = DepositService.get_settings(db)
        start = date.today()
        if s["cap_day"]:
            cap = align_capitalization_day(start, s["cap_day"])
            if cap <= start:
                start = add_months(cap, 1)
            else:
                start = cap
        return build_forecast(
            start,
            s["balance"],
            s["rate"],
            target_date,
            monthly_contribution,
            rate_schedule=s["rate_schedule"],
            capitalization_day=s["cap_day"],
        )

    @staticmethod
    def required_monthly(
        balance: Decimal,
        rate: Decimal,
        target: Decimal,
        target_date: date,
        start_date: date | None = None,
        rate_schedule: list | None = None,
        capitalization_day: int | None = None,
    ) -> Decimal:
        from app.services.deposit_calc import required_monthly_contribution

        return required_monthly_contribution(
            balance,
            rate,
            target,
            target_date,
            start_date=start_date,
            rate_schedule=rate_schedule,
            capitalization_day=capitalization_day,
        )
