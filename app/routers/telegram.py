import re
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Category, Transaction
from app.services.dashboard import DashboardService
from app.services.sinking_funds import SinkingFundService

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _is_allowed(user_id: int) -> bool:
    settings = get_settings()
    if not settings.telegram_allowed_ids:
        return False
    allowed = {int(x.strip()) for x in settings.telegram_allowed_ids.split(",") if x.strip()}
    return user_id in allowed


async def _send_message(chat_id: int, text: str) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})


@router.post("/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.telegram_bot_token:
        return {"ok": False, "error": "bot not configured"}

    data = await request.json()
    message = data.get("message") or data.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    text = (message.get("text") or "").strip()

    if not _is_allowed(user_id):
        await _send_message(chat_id, "Доступ запрещён.")
        return {"ok": True}

    if text.startswith("/start") or text.startswith("/help"):
        await _send_message(
            chat_id,
            "Команды:\n"
            "/add 1500 продукты — добавить расход\n"
            "/income 50000 — добавить доход (откроется распределение)\n"
            "/balance — баланс месяца\n"
            "/funds — статус копилок",
        )
        return {"ok": True}

    if text.startswith("/balance"):
        today = date.today()
        summary = DashboardService.get_month_summary(db, today.year, today.month)
        await _send_message(
            chat_id,
            f"Доход: {summary.income_fact:,.0f} ₽\n"
            f"Потрачено: {summary.total_spent:,.0f} ₽\n"
            f"Нераспределено: {summary.unallocated:,.0f} ₽\n"
            f"Остаток: {summary.remaining:,.0f} ₽".replace(",", " "),
        )
        return {"ok": True}

    if text.startswith("/funds"):
        summaries = SinkingFundService.get_summaries(db)
        if not summaries:
            await _send_message(chat_id, "Копилки не настроены.")
            return {"ok": True}
        lines = []
        for f in summaries:
            lines.append(
                f"{f.name}: {f.current_amount:,.0f}/{f.target_amount:,.0f} ₽".replace(",", " ")
            )
        await _send_message(chat_id, "Копилки:\n" + "\n".join(lines))
        return {"ok": True}

    add_match = re.match(r"^/add\s+([\d\s.,]+)\s+(.+)$", text, re.IGNORECASE)
    if add_match:
        try:
            amount = Decimal(add_match.group(1).replace(",", ".").replace(" ", ""))
            cat_name = add_match.group(2).strip()
        except InvalidOperation:
            await _send_message(chat_id, "Неверная сумма.")
            return {"ok": True}

        category = (
            db.query(Category)
            .filter(Category.name.ilike(f"%{cat_name}%"), Category.is_hidden.is_(False))
            .first()
        )
        tx = Transaction(
            type="expense",
            amount=amount,
            date=date.today(),
            category_id=category.id if category else None,
            comment=f"Telegram: {cat_name}",
        )
        db.add(tx)
        db.commit()
        await _send_message(chat_id, f"Расход {amount:,.0f} ₽ добавлен.".replace(",", " "))
        return {"ok": True}

    income_match = re.match(r"^/income\s+([\d\s.,]+)$", text, re.IGNORECASE)
    if income_match:
        try:
            amount = Decimal(income_match.group(1).replace(",", ".").replace(" ", ""))
        except InvalidOperation:
            await _send_message(chat_id, "Неверная сумма.")
            return {"ok": True}
        tx = Transaction(type="income", amount=amount, date=date.today(), comment="Telegram", is_fully_allocated=False)
        db.add(tx)
        db.commit()
        base_url = settings.app_base_url or "http://localhost:8000"
        await _send_message(
            chat_id,
            f"Доход {amount:,.0f} ₽ добавлен.\nРаспределить: {base_url}/allocate/{tx.id}".replace(",", " "),
        )
        return {"ok": True}

    await _send_message(chat_id, "Неизвестная команда. /help")
    return {"ok": True}
