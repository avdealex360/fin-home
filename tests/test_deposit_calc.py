"""Tests for deposit capitalization (Excel-compatible)."""

from datetime import date
from decimal import Decimal

from app.services.deposit_calc import build_forecast, deposit_step, parse_rate_schedule


def test_first_month_with_lump_sum():
    after, interest = deposit_step(Decimal("0"), Decimal("19.5"), Decimal("450000"))
    assert after == Decimal("457312.50")
    assert interest == Decimal("7312.50")


def test_second_month_no_contribution():
    after, _ = deposit_step(Decimal("457312.50"), Decimal("19.5"), Decimal("0"))
    assert after == Decimal("464743.83")


def test_rate_change_march_2026():
    schedule = parse_rate_schedule(
        '[{"from":"2025-03-18","rate":"19.5"},{"from":"2026-03-18","rate":"17.5"}]',
        Decimal("17.5"),
    )
    rows = build_forecast(
        date(2025, 3, 18),
        Decimal("0"),
        Decimal("17.5"),
        date(2026, 3, 18),
        Decimal("0"),
        initial_lump_sum=Decimal("450000"),
        rate_schedule=schedule,
        capitalization_day=18,
    )
    march_2026 = rows[12]
    assert march_2026.interest == Decimal("7962.99")
    assert march_2026.balance_after == Decimal("553996.41")


def test_full_table_feb_2027():
    schedule = parse_rate_schedule(
        '[{"from":"2025-03-18","rate":"19.5"},{"from":"2026-03-18","rate":"17.5"}]',
        Decimal("17.5"),
    )
    rows = build_forecast(
        date(2025, 3, 18),
        Decimal("0"),
        Decimal("17.5"),
        date(2027, 2, 18),
        Decimal("0"),
        initial_lump_sum=Decimal("450000"),
        rate_schedule=schedule,
        capitalization_day=18,
    )
    assert rows[-1].balance_after == Decimal("649638.74")
