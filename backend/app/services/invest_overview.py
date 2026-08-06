"""Daily AI market overview for the invest section.

Built at most once per workspace per calendar day from live MOEX data and
cached in Setting (invest.overview / invest.overview_date). Explanatory tone
for beginners; the mandatory disclaimer is appended server-side so no prompt
drift can drop it.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.ai.router import build_providers, complete_with_fallback
from app.services.moex import MoexError, Quote, get_quotes
from app.services.settings_store import get_setting, set_setting

log = logging.getLogger("invest_overview")

DISCLAIMER = "⚠️ Не является индивидуальной инвестиционной рекомендацией."

_SYSTEM = (
    "Ты — спокойный финансовый наставник для новичка, который недавно открыл ИИС. "
    "По данным Московской биржи напиши короткий обзор (3–5 предложений): что сегодня "
    "происходит с рынком и бумагами из списка, простыми словами и без жаргона. "
    "Строго запрещено советовать покупать или продавать конкретные бумаги, "
    "давать прогнозы цен и обещать доходность. Без вступлений и приветствий."
)


def _prompt(quotes: list[Quote]) -> str:
    lines = []
    for q in quotes:
        chg = f"{q.change_pct:+.2f}%" if q.change_pct is not None else "н/д"
        price = f"{q.price:,.2f}".replace(",", " ") if q.price is not None else "н/д"
        lines.append(f"{q.ticker} ({q.name}): {price}, изменение за день {chg}")
    return "Данные MOEX на сейчас:\n" + "\n".join(lines)


def get_or_build(db: Session, ws_id: int, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    today = now.date().isoformat()
    configured = bool(build_providers(db))
    if not configured:
        return {"text": None, "date": today, "configured": False}

    if get_setting(db, ws_id, "invest.overview_date", "") == today:
        cached = get_setting(db, ws_id, "invest.overview", "")
        if cached:
            return {"text": cached, "date": today, "configured": True}

    watchlist = get_setting(db, ws_id, "invest.watchlist", "IMOEX,SBER,SBMX,LQDT").split(",")
    try:
        quotes = get_quotes(watchlist)
    except MoexError as e:
        log.warning("overview: moex unavailable: %s", e)
        return {"text": None, "date": today, "configured": True}

    text, _provider = complete_with_fallback(db, _SYSTEM, _prompt(quotes), temperature=0.4)
    if not text:
        return {"text": None, "date": today, "configured": True}

    full = f"{text.strip()}\n\n{DISCLAIMER}"
    set_setting(db, ws_id, "invest.overview", full)
    set_setting(db, ws_id, "invest.overview_date", today)
    return {"text": full, "date": today, "configured": True}
