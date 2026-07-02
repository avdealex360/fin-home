from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AppUser, Category, Transaction
from app.services.ai.base import ParsedEntry


def resolve_category_id(db: Session, name: str | None) -> int | None:
    if not name:
        return None
    # Exact match (case-insensitive)
    all_cats = db.query(Category).filter(Category.is_hidden.is_(False)).all()
    for cat in all_cats:
        if cat.name.lower() == name.lower():
            return cat.id
    # Substring match (case-insensitive)
    for cat in all_cats:
        if name.lower() in cat.name.lower():
            return cat.id
    return None


def resolve_user_id(db: Session, person: str | None, sender: AppUser | None) -> int | None:
    if person:
        # Exact match (case-insensitive)
        all_users = db.query(AppUser).all()
        for user in all_users:
            if user.name.lower() == person.lower():
                return user.id
        # Check for common user markers
        if person.lower() in ("общее", "общий", "оба", "вместе"):
            for user in all_users:
                if user.name.lower().startswith("общ"):
                    return user.id
    return sender.id if sender else None


def create_transactions(
    db: Session, entries: list[ParsedEntry], sender: AppUser | None
) -> list[Transaction]:
    created: list[Transaction] = []
    for e in entries:
        cat_id = resolve_category_id(db, e.category)
        comment = e.comment
        if e.category and cat_id is None:
            note = f"категория «{e.category}»?"
            comment = f"{comment} · {note}" if comment else note
        tx = Transaction(
            type=e.type,
            amount=e.amount,
            date=e.date or date.today(),
            category_id=cat_id,
            user_id=resolve_user_id(db, e.person, sender),
            comment=comment,
        )
        db.add(tx)
        created.append(tx)
    db.commit()
    for tx in created:
        db.refresh(tx)
    return created
