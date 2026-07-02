from __future__ import annotations

import json
import random
from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models import Category, Transaction
from app.services.ai.router import complete_with_fallback
from app.services.settings_store import get_setting, set_setting

STATIC_TIPS = [
    "Правило 50/30/20: 50% на нужды, 30% на желания, 20% в накопления.",
    "Собери подушку на 3–6 месяцев расходов — это защита от форс-мажоров.",
    "Перед крупной покупкой выжди сутки: импульс часто проходит.",
    "Автоматизируй откладывание в день зарплаты — платишь сначала себе.",
    "Веди учёт хотя бы неделю — увидишь, куда реально утекают деньги.",
]

_GROUP_LABELS = {"needs": "Нужды", "wants": "Желания", "savings": "Накопления"}


def _fmt(amount: Decimal | float) -> str:
    return f"{float(amount):,.0f}".replace(",", " ")


def _collect_stats(db: Session, today: date) -> dict:
    year, month = today.year, today.month
    q = db.query(Transaction).filter(
        Transaction.type == "expense",
        extract("year", Transaction.date) == year,
        extract("month", Transaction.date) == month,
    )
    total = sum((t.amount for t in q.all()), Decimal("0"))

    by_group: dict[str, Decimal] = {}
    top_cat = (
        db.query(Category.name, func.sum(Transaction.amount).label("s"))
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.type == "expense",
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) == month,
        )
        .group_by(Category.name)
        .order_by(func.sum(Transaction.amount).desc())
        .first()
    )
    for cat, amount in (
        db.query(Category.group, func.sum(Transaction.amount))
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.type == "expense",
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) == month,
        )
        .group_by(Category.group)
        .all()
    ):
        by_group[cat] = amount or Decimal("0")

    return {
        "total": total,
        "top_category": top_cat[0] if top_cat else None,
        "top_amount": top_cat[1] if top_cat else Decimal("0"),
        "by_group": by_group,
    }


def _stats_text(stats: dict) -> str:
    lines = [f"📊 Расходы за месяц: <b>{_fmt(stats['total'])} ₽</b>"]
    if stats["top_category"]:
        lines.append(f"Топ-категория: {stats['top_category']} ({_fmt(stats['top_amount'])} ₽)")
    for g, label in _GROUP_LABELS.items():
        if g in stats["by_group"]:
            lines.append(f"{label}: {_fmt(stats['by_group'][g])} ₽")
    return "\n".join(lines)


def _build_tip(db: Session, stats: dict) -> str:
    mode = random.choice(["stats", "literacy"])
    if mode == "stats":
        system = "Ты — дружелюбный финансовый помощник. Дай один короткий персональный совет (1–2 предложения) по цифрам семьи. Без вступлений."
        user = (
            f"Расходы за месяц: {_fmt(stats['total'])} ₽. "
            f"Топ-категория: {stats['top_category']} ({_fmt(stats['top_amount'])} ₽). "
            "Дай практичный совет."
        )
    else:
        system = "Ты — финансовый просветитель. Дай один короткий совет по финансовой грамотности (1–2 предложения) на случайную тему. Без вступлений."
        user = "Тема на твой выбор: подушка, проценты, импульсивные траты, правило 50/30/20, подписки."
    tip = complete_with_fallback(db, system, user)
    return tip.strip() if tip else random.choice(STATIC_TIPS)


def get_or_build(db: Session, today: date | None = None) -> str:
    today = today or date.today()
    key = f"digest.{today.isoformat()}"
    cached = get_setting(db, key, "")
    if cached:
        data = json.loads(cached)
        return f"{data['stats_text']}\n\n💡 {data['tip_text']}"

    stats = _collect_stats(db, today)
    stats_text = _stats_text(stats)
    tip_text = _build_tip(db, stats)
    set_setting(db, key, json.dumps({"stats_text": stats_text, "tip_text": tip_text}, ensure_ascii=False))
    return f"{stats_text}\n\n💡 {tip_text}"
