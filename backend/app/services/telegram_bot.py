from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.models import AppUser, Category, Transaction
from app.services.ai.base import ParseContext
from app.services.ai.router import parse_with_fallback, provider_label
from app.services.daily_digest import get_or_build as build_digest
from app.services.settings_store import get_secret, get_setting
from app.services.tg_client import answer_callback_query, send_message
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

_COMMANDS_KB = {
    "keyboard": [["📊 Статистика", "↩️ Отменить", "❓ Помощь"]],
    "resize_keyboard": True,
    "is_persistent": True,
}
_BUTTON_TO_CMD = {
    "📊 Статистика": "/stats",
    "↩️ Отменить": "/undo",
    "❓ Помощь": "/help",
}


def _sender(db: Session, tg_id: str) -> AppUser | None:
    return db.query(AppUser).filter(AppUser.telegram_id == tg_id).first()


def _money(x) -> str:
    return f"{float(x):,.0f}".replace(",", " ")


def _category_keyboard(db: Session, tx_id: int) -> dict:
    cats = (
        db.query(Category)
        .filter(Category.is_hidden.is_(False), Category.group != "income")
        .order_by(Category.sort_order, Category.id)
        .all()
    )
    buttons = [{"text": c.name, "callback_data": f"setcat:{tx_id}:{c.id}"} for c in cats]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return {"inline_keyboard": rows}


def handle_update(db: Session, update: dict) -> None:
    try:
        cb = update.get("callback_query")
        if cb:
            _handle_callback(db, cb)
            return
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return
        text = (msg.get("text") or "").strip()
        text = _BUTTON_TO_CMD.get(text, text)
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
            send_message(token, chat_id, _HELP, reply_markup=_COMMANDS_KB)
            return
        if text == "/stats":
            send_message(token, chat_id, build_digest(db), reply_markup=_COMMANDS_KB)
            return
        if text == "/undo":
            _handle_undo(db, token, chat_id, tg_id)
            return
        if not text:
            return

        log.info("telegram.incoming tg_id=%s text=%r", tg_id, text)
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
    entries, provider = parse_with_fallback(db, text, ctx)
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
    if provider:
        lines.append(f"🧠 {provider_label(provider)}")
    send_message(token, chat_id, "\n".join(lines), reply_markup=_COMMANDS_KB)
    for t, e in zip(txs, entries):
        if t.category_id is None:
            label = e.comment or text
            send_message(
                token, chat_id,
                f"❓ Категория для «{_money(t.amount)} ₽ — {label}»?",
                reply_markup=_category_keyboard(db, t.id),
            )


def _handle_undo(db, token, chat_id, tg_id) -> None:
    ids = _LAST_BATCH.pop(tg_id, [])
    if not ids:
        send_message(token, chat_id, "Нечего отменять.", reply_markup=_COMMANDS_KB)
        return
    db.query(Transaction).filter(Transaction.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    send_message(token, chat_id, f"↩️ Удалено операций: {len(ids)}.", reply_markup=_COMMANDS_KB)


def _handle_callback(db, cb) -> None:
    token = get_secret(db, "secret.tg_bot_token")
    if not token:
        return
    cb_id = cb["id"]
    tg_id = str(cb["from"]["id"])
    chat_id = cb.get("message", {}).get("chat", {}).get("id", tg_id)
    data = cb.get("data", "")
    if _sender(db, tg_id) is None:
        answer_callback_query(token, cb_id, "Нет доступа")
        return
    if data.startswith("setcat:"):
        try:
            _, tx_s, cat_s = data.split(":")
            tx = db.get(Transaction, int(tx_s))
            cat = db.get(Category, int(cat_s))
        except (ValueError, KeyError):
            answer_callback_query(token, cb_id, "")
            return
        if not tx or not cat:
            answer_callback_query(token, cb_id, "Операция не найдена")
            return
        tx.category_id = cat.id
        db.commit()
        answer_callback_query(token, cb_id, f"✅ {cat.name}")
        send_message(token, chat_id, f"✅ Категория: {cat.name} — {_money(tx.amount)} ₽")
        return
    answer_callback_query(token, cb_id, "")
