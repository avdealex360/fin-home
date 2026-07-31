from __future__ import annotations

import json
import random
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models import Category, Transaction
from app.services.ai.router import complete_with_fallback, provider_label
from app.services.settings_store import get_setting, set_setting

STATIC_TIPS = [
    "Правило 50/30/20: 50% на нужды, 30% на желания, 20% в накопления.",
    "Собери подушку на 3–6 месяцев расходов — это защита от форс-мажоров.",
    "Перед крупной покупкой выжди сутки: импульс часто проходит.",
    "Автоматизируй откладывание в день зарплаты — платишь сначала себе.",
    "Веди учёт хотя бы неделю — увидишь, куда реально утекают деньги.",
    "Подписки — тихий враг бюджета: раз в квартал сверяй, чем реально пользуешься.",
    "Сложный процент работает и на тебя, и против тебя — в накоплениях и в кредитах одинаково.",
    "Крупную покупку дели на «хочу» и «нужно» — вопрос вслух отрезвляет.",
    "Кэшбэк — не доход, а скидка. Не покупай ради него то, что не планировал.",
    "Заведи отдельный счёт для целей — глаза не мозолит, рука не тянется.",
]

_LITERACY_TOPICS = [
    "финансовая подушка безопасности",
    "сложные проценты",
    "импульсивные покупки",
    "правило 50/30/20",
    "ненужные подписки",
    "кредитные карты и рассрочки",
    "инвестиции для новичков",
    "инфляция и почему деньги обесцениваются",
    "разница между «тратить» и «инвестировать»",
    "как копить, если денег в обрез",
    "ловушка рассрочки «0%»",
    "почему нельзя хранить все деньги в одном месте",
    "кэшбэк и скрытая переплата",
    "финансовые цели вместо абстрактного «копить»",
]

_STYLES = [
    "с лёгким юмором",
    "в виде яркой метафоры или неожиданного сравнения",
    "как дружеский совет от бывалого товарища",
    "коротко и дерзко, без воды",
    "с сравнением из повседневной жизни (кухня, транспорт, спорт)",
    "с щепоткой самоиронии",
    "в виде маленькой сценки или мини-истории",
]

_GROUP_LABELS = {"needs": "Нужды", "wants": "Желания", "savings": "Накопления"}


def _fmt(amount: Decimal | float) -> str:
    return f"{float(amount):,.0f}".replace(",", " ")


def _collect_stats(db: Session, ws_id: int, today: date) -> dict:
    year, month = today.year, today.month
    q = db.query(Transaction).filter(
        Transaction.workspace_id == ws_id,
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
            Transaction.workspace_id == ws_id,
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
            Transaction.workspace_id == ws_id,
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


def _build_tip(db: Session, stats: dict) -> tuple[str, str | None]:
    mode = random.choice(["stats", "literacy", "story"])
    style = random.choice(_STYLES)
    if mode == "stats":
        system = (
            "Ты — остроумный финансовый помощник семьи. Дай один короткий персональный совет "
            f"(1–2 предложения) по цифрам семьи, {style}. Будь живым и не банальным, избегай "
            "канцелярита и заезженных фраз. Без вступлений и приветствий."
        )
        user = (
            f"Расходы за месяц: {_fmt(stats['total'])} ₽. "
            f"Топ-категория: {stats['top_category']} ({_fmt(stats['top_amount'])} ₽). "
            "Дай практичный, но живой совет."
        )
    elif mode == "literacy":
        topic = random.choice(_LITERACY_TOPICS)
        system = (
            "Ты — финансовый просветитель с фантазией. Дай один короткий совет по финансовой "
            f"грамотности (1–2 предложения) на заданную тему, {style}. Придумай свежую "
            "формулировку, не повторяй шаблонные фразы вроде «откладывайте 10%». Без вступлений."
        )
        user = f"Тема: {topic}."
    else:
        topic = random.choice(_LITERACY_TOPICS)
        system = (
            "Ты — рассказчик с богатым воображением, который объясняет финансы через маленькие "
            "яркие образы. Придумай одну короткую (1–2 предложения) метафору или мини-сценку из "
            f"жизни, которая доносит мысль о теме, {style}. Без вступлений и морали в духе «итак»."
        )
        user = f"Тема: {topic}."
    tip, provider = complete_with_fallback(db, system, user, temperature=0.9)
    if tip:
        return tip.strip(), provider
    return random.choice(STATIC_TIPS), None


def _format_digest(stats_text: str, tip_text: str, tip_provider: str | None) -> str:
    footer = f"\n🧠 {provider_label(tip_provider)}" if tip_provider else ""
    return f"{stats_text}\n\n💡 {tip_text}{footer}"


def get_or_build(db: Session, ws_id: int, now: datetime | None = None) -> str:
    now = now or datetime.now()
    today = now.date()
    # Hourly bucket: the AI tip rotates every hour, stats below are always recomputed live.
    key = f"digest.{now.strftime('%Y-%m-%dT%H')}"

    stats = _collect_stats(db, ws_id, today)
    stats_text = _stats_text(stats)

    cached = get_setting(db, ws_id, key, "")
    if cached:
        data = json.loads(cached)
        return _format_digest(stats_text, data["tip_text"], data.get("tip_provider"))

    tip_text, tip_provider = _build_tip(db, stats)
    set_setting(
        db,
        ws_id,
        key,
        json.dumps(
            {"tip_text": tip_text, "tip_provider": tip_provider},
            ensure_ascii=False,
        ),
    )
    return _format_digest(stats_text, tip_text, tip_provider)
