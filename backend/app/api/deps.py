"""Shared API helpers."""

from datetime import date

from fastapi import HTTPException, Query, Request


def ws_id(request: Request) -> int:
    """Workspace of the authenticated account, resolved by the auth middleware."""
    ws = getattr(request.state, "workspace_id", None)
    if ws is None:
        raise HTTPException(401, "Unauthorized")
    return ws


def require_admin(request: Request) -> int:
    """Account id of the authenticated admin; 403 for everyone else."""
    if not getattr(request.state, "is_admin", False):
        raise HTTPException(403, "Admin only")
    return request.state.account_id


def current_ym() -> tuple[int, int]:
    today = date.today()
    return today.year, today.month


def ym_params(
    year: int | None = Query(None),
    month: int | None = Query(None),
) -> tuple[int, int]:
    cy, cm = current_ym()
    return year or cy, month or cm
