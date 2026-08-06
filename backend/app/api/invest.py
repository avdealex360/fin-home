"""Инвестиции: котировки MOEX по watchlist воркспейса + дневной AI-обзор.

Справочный раздел — на бюджет не влияет, состояние живёт в Setting.
"""
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.api.deps import ws_id
from app.db import get_db
from app.services import invest_overview
from app.services.moex import MoexError, get_quotes
from app.services.settings_store import get_setting, set_setting

router = APIRouter(prefix="/api/invest", tags=["invest"])

DEFAULT_WATCHLIST = "IMOEX,SBER,SBMX,LQDT"
_TICKER_RE = re.compile(r"^[A-Z0-9]{1,12}$")


def _watchlist(db: Session, ws: int) -> list[str]:
    stored = get_setting(db, ws, "invest.watchlist", "")
    if not stored:
        set_setting(db, ws, "invest.watchlist", DEFAULT_WATCHLIST)
        stored = DEFAULT_WATCHLIST
    return stored.split(",")


class WatchlistBody(BaseModel):
    tickers: list[str]

    @field_validator("tickers")
    @classmethod
    def check(cls, v: list[str]) -> list[str]:
        v = [t.strip().upper() for t in v]
        if not 1 <= len(v) <= 20:
            raise ValueError("1..20 tickers")
        for t in v:
            if not _TICKER_RE.match(t):
                raise ValueError(f"bad ticker: {t!r}")
        return v


@router.get("/watchlist")
def get_watchlist(db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    return {"tickers": _watchlist(db, ws)}


@router.put("/watchlist")
def put_watchlist(body: WatchlistBody, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    set_setting(db, ws, "invest.watchlist", ",".join(body.tickers))
    return {"tickers": body.tickers}


@router.get("/overview")
def overview(db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    return invest_overview.get_or_build(db, ws)


@router.get("/market")
def market(db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    tickers = _watchlist(db, ws)
    try:
        quotes = get_quotes(tickers)
    except MoexError as e:
        return {"quotes": [], "error": str(e)}
    return {
        "quotes": [
            {"ticker": q.ticker, "name": q.name, "price": q.price, "change_pct": q.change_pct}
            for q in quotes
        ],
        "error": None,
    }
