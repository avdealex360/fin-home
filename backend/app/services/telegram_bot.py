from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.models import AppUser, Category, Transaction
from app.services.ai.base import ParseContext
from app.services.ai.router import parse_with_fallback
from app.services.daily_digest import get_or_build as build_digest
from app.services.settings_store import get_secret, get_setting
from app.services.tg_client import send_message
from app.services.tx_resolver import create_transactions

log = logging.getLogger("telegram_bot")

# Per-sender id of the last written batch, for /undo. In-memory only.
_LAST_BATCH: dict[str, list[int]] = {}

_HELP = (
    "Пришли трату свободным текстом, например:\n"
    "<i>магазин 1560, кофе 360, интернет 1200</i>\n\n"
    "Команды:\n"
    "/stats — статистика и совет дня\n"
    "/undo — отменить последнюю запись\n"
    "/help — эта справка"
)


def _sender(db: Session, tg_id: str) -> AppUser | None:
    return db.query(AppUser).filter(AppUser.telegram_id == tg_id).first()


def handle_update(db: Session, update: dict) -> None:
    try:
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return
        text = (msg.get("text") or "").strip()
        chat_id = msg["chat"]["id"]
        tg_id = str(msg["from"]["id"])
        token = get_secret(db, "secret.tg_bot_token")
        if not token:
            log.warning("no bot token configured")
            return

        sender = _sender(db, tg_id)
        if sender is None:
            send_message(token, chat_id,
                         f"Аккаунт не привязан. Твой Telegram ID: <code>{tg_id}</code>. "
                         "Впиши его в приложении (More → Интеграции).")
            return

        if text in ("/start", "/help"):
            send_message(token, chat_id, _HELP)
            return
        if text == "/stats":
            send_message(token, chat_id, build_digest(db))
            return
        if text == "/undo":
            _handle_undo(db, token, chat_id, tg_id)
            return
        if not text:
            return

        _handle_text(db, token, chat_id, tg_id, sender, text)
    except Exception:  # webhook must never raise
        log.exception("handle_update failed")


def _handle_text(db, token, chat_id, tg_id, sender, text) -> None:
    ctx = ParseContext(
        categories=[
            {"id": c.id, "name": c.name, "group": c.group}
            for c in db.query(Category).filter(Category.is_hidden.is_(False)).all()
        ],
        users=[u.name for u in db.query(AppUser).filter(AppUser.is_active.is_(True)).all()],
        sender_name=sender.name,
        today=date.today(),
        currency=get_setting(db, "currency", "RUB"),
    )
    entries = parse_with_fallback(db, text, ctx)
    if not entries:
        send_message(token, chat_id, "Не смог разобрать 🤔 Попробуй иначе: «кофе 360, магазин 1560».")
        return

    txs = create_transactions(db, entries, sender)
    _LAST_BATCH[tg_id] = [t.id for t in txs]

    total = sum(t.amount for t in txs)
    lines = [f"✅ {len(txs)} операц. на <b>{float(total):,.0f}".replace(",", " ") + " ₽</b>"]
    for t, e in zip(txs, entries):
        cat = db.get(Category, t.category_id).name if t.category_id else "без категории"
        warn = " ⚠️ проверь" if (e.confidence != "high" or t.category_id is None) else ""
        lines.append(f"• {float(t.amount):,.0f}".replace(",", " ") + f" ₽ — {cat}{warn}")
    send_message(token, chat_id, "\n".join(lines))


def _handle_undo(db, token, chat_id, tg_id) -> None:
    ids = _LAST_BATCH.pop(tg_id, [])
    if not ids:
        send_message(token, chat_id, "Нечего отменять.")
        return
    db.query(Transaction).filter(Transaction.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    send_message(token, chat_id, f"↩️ Удалено операций: {len(ids)}.")
