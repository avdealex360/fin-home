"""Onboarding, lookups (users/categories) and the dashboard summary."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import ws_id, ym_params
from app.db import get_db
from app.models import (
    AppUser,
    Category,
    CategoryLimit,
    PlannedExpense,
    Transaction,
)
from app.seed import is_onboarded, load_clean_start, load_demo_data
from app.serializers import category_dict, user_dict
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/api", tags=["meta"])


# ---- onboarding ----
class OnboardBody(BaseModel):
    mode: str  # "demo" | "clean"


@router.get("/onboarding")
def onboarding_status(db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    return {"onboarded": is_onboarded(db, ws)}


@router.post("/onboarding")
def onboard(body: OnboardBody, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    if body.mode == "demo":
        load_demo_data(db, ws)
    elif body.mode == "clean":
        load_clean_start(db, ws)
    else:
        raise HTTPException(400, "mode must be 'demo' or 'clean'")
    return {"onboarded": True, "mode": body.mode}


# ---- users ----
class UserBody(BaseModel):
    name: str
    telegram_id: str | None = None


@router.get("/users")
def list_users(db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    users = (
        db.query(AppUser)
        .filter(AppUser.workspace_id == ws, AppUser.is_active.is_(True))
        .order_by(AppUser.id)
        .all()
    )
    return [user_dict(u) for u in users]


@router.post("/users")
def create_user(body: UserBody, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    u = AppUser(workspace_id=ws, name=body.name, telegram_id=body.telegram_id or None)
    db.add(u)
    db.commit()
    db.refresh(u)
    return user_dict(u)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserBody, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    u = db.query(AppUser).filter(AppUser.id == user_id, AppUser.workspace_id == ws).first()
    if not u:
        raise HTTPException(404, "user not found")
    u.name = body.name
    u.telegram_id = body.telegram_id or None
    db.commit()
    db.refresh(u)
    return user_dict(u)


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    u = db.query(AppUser).filter(AppUser.id == user_id, AppUser.workspace_id == ws).first()
    if u:
        u.is_active = False
        db.commit()
    return {"ok": True}


# ---- categories ----
class CategoryBody(BaseModel):
    name: str
    group: str  # needs | wants | savings | income
    sort_order: int | None = None
    is_hidden: bool | None = None
    icon: str | None = None  # ti-* name; empty string resets to the default


@router.get("/categories")
def list_categories(
    include_hidden: bool = False,
    group: str | None = None,
    db: Session = Depends(get_db),
    ws: int = Depends(ws_id),
):
    q = db.query(Category).filter(Category.workspace_id == ws)
    if not include_hidden:
        q = q.filter(Category.is_hidden.is_(False))
    if group:
        q = q.filter(Category.group == group)
    cats = q.order_by(Category.sort_order, Category.id).all()
    return [category_dict(c) for c in cats]


@router.post("/categories")
def create_category(body: CategoryBody, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    max_order = db.query(Category).filter(Category.workspace_id == ws).count()
    c = Category(
        workspace_id=ws,
        name=body.name,
        group=body.group,
        sort_order=body.sort_order if body.sort_order is not None else max_order + 1,
        icon=body.icon or None,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return category_dict(c)


@router.patch("/categories/{cat_id}")
def update_category(cat_id: int, body: CategoryBody, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    c = db.query(Category).filter(Category.id == cat_id, Category.workspace_id == ws).first()
    if not c:
        raise HTTPException(404, "category not found")
    c.name = body.name
    c.group = body.group
    if body.sort_order is not None:
        c.sort_order = body.sort_order
    if body.is_hidden is not None:
        c.is_hidden = body.is_hidden
    if body.icon is not None:
        c.icon = body.icon or None
    db.commit()
    db.refresh(c)
    return category_dict(c)


@router.delete("/categories/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    """Hard-delete only when truly unused, otherwise hide.

    A category can be referenced from several tables (transactions, plan
    limits, planned expenses). If any *historical* record points to it we
    hide it to keep reports intact. Plan-only artifacts (limits / planned
    expenses) are just configuration — we clean them up so an unused
    category can still be removed instead of raising a FK error.
    """
    c = db.query(Category).filter(Category.id == cat_id, Category.workspace_id == ws).first()
    if not c:
        return {"ok": True}

    has_history = db.query(Transaction.id).filter(Transaction.category_id == cat_id).first()
    if has_history:
        c.is_hidden = True
        db.commit()
        return {"ok": True, "hidden": True}

    # No historical data — drop plan-only references, then hard-delete.
    db.query(CategoryLimit).filter(CategoryLimit.category_id == cat_id).delete(
        synchronize_session=False
    )
    db.query(PlannedExpense).filter(PlannedExpense.category_id == cat_id).update(
        {PlannedExpense.category_id: None}, synchronize_session=False
    )
    db.delete(c)
    db.commit()
    return {"ok": True, "deleted": True}


# ---- dashboard ----
@router.get("/dashboard")
def dashboard(
    ym: tuple[int, int] = Depends(ym_params),
    db: Session = Depends(get_db),
    ws: int = Depends(ws_id),
):
    year, month = ym
    summary = DashboardService.get_month_summary(db, ws, year, month)
    return summary
