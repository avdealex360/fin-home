"""Shared API helpers."""

from datetime import date

from fastapi import Query


def current_ym() -> tuple[int, int]:
    today = date.today()
    return today.year, today.month


def ym_params(
    year: int | None = Query(None),
    month: int | None = Query(None),
) -> tuple[int, int]:
    cy, cm = current_ym()
    return year or cy, month or cm
