#!/usr/bin/env python3
"""Cron script: evaluate rules and send Telegram notifications."""

import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.db import SessionLocal
from app.routers.telegram import _send_message
from app.services.rules import RuleEngine


async def main() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_allowed_ids:
        print("Telegram not configured, skipping.")
        return

    today = date.today()
    db = SessionLocal()
    try:
        advice_list = RuleEngine.evaluate(db, today.year, today.month, max_advice=5)
        if not advice_list:
            return
        text = "Советы по бюджету:\n\n" + "\n".join(f"• {a.message}" for a in advice_list)
        for user_id in settings.telegram_allowed_ids.split(","):
            uid = user_id.strip()
            if uid:
                await _send_message(int(uid), text)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
