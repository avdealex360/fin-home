from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.settings_store import get_secret
from app.services.telegram_bot import handle_update

router = APIRouter(prefix="/api/tg", tags=["telegram"])
log = logging.getLogger("app.tg_webhook")


@router.post("/webhook/{secret}")
async def webhook(
    secret: str,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    expected = get_secret(db, "secret.tg_webhook_secret")
    if (
        not expected
        or not hmac.compare_digest(secret, expected)
        or not hmac.compare_digest(x_telegram_bot_api_secret_token or "", expected)
    ):
        return JSONResponse({"detail": "forbidden"}, status_code=403)
    update = await request.json()
    msg = update.get("message") or update.get("edited_message") or {}
    text = (msg.get("text") or "")[:120]
    log.info(
        "webhook hit update_id=%s tg_id=%s text=%r",
        update.get("update_id"),
        msg.get("from", {}).get("id"),
        text or update.get("callback_query", {}).get("data", ""),
    )
    handle_update(db, update)
    return {"ok": True}
