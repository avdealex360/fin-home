from __future__ import annotations

from datetime import date
from decimal import Decimal
import re

from sqlalchemy.orm import Session

from app.models import AppUser, Category, Transaction
from app.services.ai.base import ParsedEntry, _normalize_category_name

_GROUP_TOKENS = frozenset({"needs", "wants", "savings", "income", "нужды", "желания", "накопления"})

_TOKEN_TO_GROUP = {
    "needs": "needs",
    "нужды": "needs",
    "wants": "wants",
    "желания": "wants",
    "savings": "savings",
    "накопления": "savings",
    "income": "income",
}

# (keywords in hint text, substrings that must appear in category name)
_HINT_RULES: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("бойлер", "ремонт", "газ", "жиль", "квартир", "коммунал", "жкх"), ("квартир", "жиль")),
    (("табак", "кальян", "сигарет", "вейп"), ("ресторан", "доставк", "развлечен", "подписк")),
    (("облако", "хостинг", "сервер", "яндекс", "интернет", "связь", "облак"), ("связь", "интернет")),
    (("корм", "кот", "кошк", "питом"), ("кот", "питом")),
]


def _hint_from_source(amount: Decimal, source_text: str) -> str:
    """Text fragment for this amount: from previous comma/amount to the digits."""
    if not source_text:
        return ""
    amt = str(int(amount))
    idx = source_text.find(amt)
    if idx < 0:
        return ""
    before = source_text[:idx]
    comma_idx = max(before.rfind(","), before.rfind("，"))
    if comma_idx >= 0:
        start = comma_idx + 1
    else:
        prev_nums = list(re.finditer(r"\d+", before))
        start = prev_nums[-1].end() if prev_nums else 0
    return source_text[start : idx + len(amt)].strip()


def _comment_from_hint(hint: str, amount: Decimal) -> str | None:
    """Derive a short comment from source text when AI left comment empty."""
    if not hint:
        return None
    amt = str(int(amount))
    text = hint
    if text.endswith(amt):
        text = text[: -len(amt)].rstrip(" ,.;–-")
    text = text.strip(" ,.")
    return text or None


def _guess_category_id(db: Session, ws_id: int, group: str, hint: str) -> int | None:
    hint_l = hint.lower()
    if not hint_l:
        return None
    cats = (
        db.query(Category)
        .filter(Category.workspace_id == ws_id, Category.is_hidden.is_(False), Category.group == group)
        .order_by(Category.sort_order, Category.id)
        .all()
    )
    for keywords, name_parts in _HINT_RULES:
        if any(k in hint_l for k in keywords):
            for cat in cats:
                name_l = cat.name.lower()
                if any(p in name_l for p in name_parts):
                    return cat.id
    return None


def resolve_category_id(
    db: Session,
    ws_id: int,
    name: str | None,
    comment: str | None = None,
    *,
    hint: str | None = None,
) -> int | None:
    blob = " ".join(filter(None, [hint, comment, name]))
    if not blob.strip():
        return None

    all_cats = (
        db.query(Category)
        .filter(Category.workspace_id == ws_id, Category.is_hidden.is_(False))
        .all()
    )

    if name:
        name = _normalize_category_name(name) or name
        name_l = name.strip().lower()
        if name_l in _GROUP_TOKENS:
            group = _TOKEN_TO_GROUP.get(name_l)
            if group:
                guessed = _guess_category_id(db, ws_id, group, blob)
                if guessed:
                    return guessed
        else:
            for cat in all_cats:
                if cat.name.lower() == name_l:
                    return cat.id
            for cat in all_cats:
                if name_l in cat.name.lower() or cat.name.lower() in name_l:
                    return cat.id

    # No valid name — try keyword guess on comment/hint only (default group needs)
    for group in ("needs", "wants", "savings"):
        guessed = _guess_category_id(db, ws_id, group, blob)
        if guessed:
            return guessed
    return None


def resolve_user_id(db: Session, ws_id: int, person: str | None, sender: AppUser | None) -> int | None:
    if person:
        all_users = db.query(AppUser).filter(AppUser.workspace_id == ws_id).all()
        for user in all_users:
            if user.name.lower() == person.lower():
                return user.id
        if person.lower() in ("общее", "общий", "оба", "вместе"):
            for user in all_users:
                if user.name.lower().startswith("общ"):
                    return user.id
    return sender.id if sender else None


def create_transactions(
    db: Session,
    ws_id: int,
    entries: list[ParsedEntry],
    sender: AppUser | None,
    source_text: str | None = None,
) -> list[Transaction]:
    created: list[Transaction] = []
    for e in entries:
        hint = _hint_from_source(e.amount, source_text or "")
        cat_id = resolve_category_id(db, ws_id, e.category, e.comment, hint=hint)
        comment = e.comment or _comment_from_hint(hint, e.amount)
        if e.category and cat_id is None:
            note = f"категория «{e.category}»?"
            comment = f"{comment} · {note}" if comment else note
        tx = Transaction(
            workspace_id=ws_id,
            type=e.type,
            amount=e.amount,
            date=e.date or date.today(),
            category_id=cat_id,
            user_id=resolve_user_id(db, ws_id, e.person, sender),
            comment=comment,
        )
        db.add(tx)
        created.append(tx)
    db.commit()
    for tx in created:
        db.refresh(tx)
    return created
