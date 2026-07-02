from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.settings_store import get_secret
from app.services.telegram_bot import handle_update

router = APIRouter(prefix="/api/tg", tags=["telegram"])


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
    handle_update(db, update)
    return {"ok": True}
