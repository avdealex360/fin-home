"""App settings (currency), data export."""

import csv
import io
import json
import secrets as secrets_mod

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_admin, ws_id
from app.config import get_settings as get_app_settings
from app.db import get_db
from app.models import Setting, Transaction
from app.serializers import (
    category_dict,
    debt_dict,
    fund_dict,
    transaction_dict,
)
from app.services.ai.router import build_providers
from app.services.settings_store import (
    get_secret,
    get_setting,
    mask_secret,
    secret_is_set,
    set_secret,
    set_setting,
)
from app.services.tg_client import TgError, get_me, set_webhook

router = APIRouter(prefix="/api/settings", tags=["settings"])


class GeneralBody(BaseModel):
    currency: str | None = None


@router.get("")
def get_settings(db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    from app.seed import is_onboarded

    return {
        "currency": get_setting(db, ws, "currency", ""),
        "onboarded": is_onboarded(db, ws),
    }


@router.post("/general")
def update_general(body: GeneralBody, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    for key, value in body.model_dump(exclude_none=True).items():
        set_setting(db, ws, key, value)
    return {"ok": True}


@router.get("/export/json")
def export_json(db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    from app.models import AppUser, Category, Debt, SinkingFund

    data = {
        "categories": [category_dict(c) for c in db.query(Category).filter(Category.workspace_id == ws).all()],
        "transactions": [transaction_dict(t) for t in db.query(Transaction).filter(Transaction.workspace_id == ws).all()],
        "debts": [debt_dict(d) for d in db.query(Debt).filter(Debt.workspace_id == ws).all()],
        "funds": [fund_dict(f) for f in db.query(SinkingFund).filter(SinkingFund.workspace_id == ws).all()],
        "users": [{"id": u.id, "name": u.name} for u in db.query(AppUser).filter(AppUser.workspace_id == ws).all()],
        "settings": {
            s.key: s.value
            for s in db.query(Setting).filter(Setting.workspace_id == ws).all()
            if not s.key.startswith("secret.")
        },
    }
    buf = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    return StreamingResponse(
        buf,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=fin-home-export.json"},
    )


@router.get("/export/csv")
def export_csv(db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["date", "type", "amount", "category", "user", "comment"])
    rows = (
        db.query(Transaction)
        .filter(Transaction.workspace_id == ws)
        .order_by(Transaction.date)
        .all()
    )
    for t in rows:
        writer.writerow(
            [
                t.date.isoformat() if t.date else "",
                t.type,
                float(t.amount),
                t.category.name if t.category else "",
                t.user.name if t.user else "",
                t.comment or "",
            ]
        )
    buf = io.BytesIO(out.getvalue().encode("utf-8-sig"))
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fin-home-transactions.csv"},
    )


_SECRET_FIELDS = ["tg_bot_token", "yandex_api_key", "yandex_folder_id", "gigachat_auth_key"]


class IntegrationsBody(BaseModel):
    tg_bot_token: str | None = None
    yandex_api_key: str | None = None
    yandex_folder_id: str | None = None
    gigachat_auth_key: str | None = None
    ai_primary_provider: str | None = None
    tg_bot_enabled: bool | None = None


@router.get("/integrations")
def get_integrations(db: Session = Depends(get_db), _admin: int = Depends(require_admin)):
    out = {f: secret_is_set(db, f"secret.{f}") for f in _SECRET_FIELDS}
    out["tg_bot_token_mask"] = mask_secret(get_secret(db, "secret.tg_bot_token"))
    out["ai_primary_provider"] = get_setting(db, None, "ai_primary_provider", "yandex")
    out["tg_bot_enabled"] = get_setting(db, None, "tg_bot_enabled", "") == "1"
    out["webhook_set"] = secret_is_set(db, "secret.tg_webhook_secret")
    return out


@router.post("/integrations")
def save_integrations(body: IntegrationsBody, db: Session = Depends(get_db), _admin: int = Depends(require_admin)):
    for f in _SECRET_FIELDS:
        val = getattr(body, f)
        if val is not None:
            set_secret(db, f"secret.{f}", val)
    if body.ai_primary_provider in ("yandex", "gigachat"):
        set_setting(db, None, "ai_primary_provider", body.ai_primary_provider)
    if body.tg_bot_enabled is not None:
        set_setting(db, None, "tg_bot_enabled", "1" if body.tg_bot_enabled else "")
    return {"ok": True}


@router.post("/integrations/test")
def test_integrations(db: Session = Depends(get_db), _admin: int = Depends(require_admin)):
    result = {"telegram": False, "yandex": False, "gigachat": False}
    token = get_secret(db, "secret.tg_bot_token")
    if token:
        try:
            get_me(token)
            result["telegram"] = True
        except TgError:
            result["telegram"] = False
    for provider in build_providers(db):
        result[provider.name] = provider.healthcheck()
    return result


@router.post("/integrations/set-webhook")
def set_bot_webhook(db: Session = Depends(get_db), _admin: int = Depends(require_admin)):
    token = get_secret(db, "secret.tg_bot_token")
    if not token:
        return {"ok": False, "url": "", "error": "no bot token"}
    base = get_app_settings().app_base_url.rstrip("/")
    if not base:
        return {"ok": False, "url": "", "error": "APP_BASE_URL not set"}
    webhook_secret = get_secret(db, "secret.tg_webhook_secret")
    if not webhook_secret:
        webhook_secret = secrets_mod.token_urlsafe(24)
        set_secret(db, "secret.tg_webhook_secret", webhook_secret)
    url = f"{base}/api/tg/webhook/{webhook_secret}"
    try:
        set_webhook(token, url, webhook_secret)
        return {"ok": True, "url": url}
    except TgError as e:
        return {"ok": False, "url": url, "error": str(e)}
