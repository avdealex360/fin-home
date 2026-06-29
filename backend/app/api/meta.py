"""Onboarding, lookups (users/categories) and the dashboard summary + advice."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import ym_params
from app.db import get_db
from app.models import AppUser, Category, Transaction
from app.seed import is_onboarded, load_clean_start, load_demo_data
from app.serializers import category_dict, user_dict
from app.services.dashboard import DashboardService
from app.services.rules import RuleEngine

router = APIRouter(prefix="/api", tags=["meta"])


# ---- onboarding ----
class OnboardBody(BaseModel):
    mode: str  # "demo" | "clean"


@router.get("/onboarding")
def onboarding_status(db: Session = Depends(get_db)):
    return {"onboarded": is_onboarded(db)}


@router.post("/onboarding")
def onboard(body: OnboardBody, db: Session = Depends(get_db)):
    if body.mode == "demo":
        load_demo_data(db)
    elif body.mode == "clean":
        load_clean_start(db)
    else:
        raise HTTPException(400, "mode must be 'demo' or 'clean'")
    return {"onboarded": True, "mode": body.mode}


# ---- users ----
class UserBody(BaseModel):
    name: str


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(AppUser).filter(AppUser.is_active.is_(True)).order_by(AppUser.id).all()
    return [user_dict(u) for u in users]


@router.post("/users")
def create_user(body: UserBody, db: Session = Depends(get_db)):
    u = AppUser(name=body.name)
    db.add(u)
    db.commit()
    db.refresh(u)
    return user_dict(u)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserBody, db: Session = Depends(get_db)):
    u = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not u:
        raise HTTPException(404, "user not found")
    u.name = body.name
    db.commit()
    db.refresh(u)
    return user_dict(u)


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    u = db.query(AppUser).filter(AppUser.id == user_id).first()
    if u:
        u.is_active = False
        db.commit()
    return {"ok": True}


# ---- categories ----
class CategoryBody(BaseModel):
    name: str
    group: str  # needs | wants | savings | income
    allocation_level: int | None = None
    sort_order: int | None = None


@router.get("/categories")
def list_categories(
    include_hidden: bool = False,
    group: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Category)
    if not include_hidden:
        q = q.filter(Category.is_hidden.is_(False))
    if group:
        q = q.filter(Category.group == group)
    cats = q.order_by(Category.sort_order, Category.id).all()
    return [category_dict(c) for c in cats]


@router.post("/categories")
def create_category(body: CategoryBody, db: Session = Depends(get_db)):
    max_order = db.query(Category).count()
    c = Category(
        name=body.name,
        group=body.group,
        allocation_level=body.allocation_level,
        sort_order=body.sort_order if body.sort_order is not None else max_order + 1,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return category_dict(c)


@router.patch("/categories/{cat_id}")
def update_category(cat_id: int, body: CategoryBody, db: Session = Depends(get_db)):
    c = db.query(Category).filter(Category.id == cat_id).first()
    if not c:
        raise HTTPException(404, "category not found")
    c.name = body.name
    c.group = body.group
    if body.allocation_level is not None:
        c.allocation_level = body.allocation_level
    if body.sort_order is not None:
        c.sort_order = body.sort_order
    db.commit()
    db.refresh(c)
    return category_dict(c)


@router.delete("/categories/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(get_db)):
    """Hard-delete if unused, otherwise hide (keeps historical transactions intact)."""
    c = db.query(Category).filter(Category.id == cat_id).first()
    if not c:
        return {"ok": True}
    used = db.query(Transaction).filter(Transaction.category_id == cat_id).first()
    if used:
        c.is_hidden = True
        db.commit()
        return {"ok": True, "hidden": True}
    db.delete(c)
    db.commit()
    return {"ok": True, "deleted": True}


# ---- dashboard ----
@router.get("/dashboard")
def dashboard(ym: tuple[int, int] = Depends(ym_params), db: Session = Depends(get_db)):
    year, month = ym
    summary = DashboardService.get_month_summary(db, year, month)
    return summary


@router.get("/advice")
def advice(ym: tuple[int, int] = Depends(ym_params), db: Session = Depends(get_db)):
    year, month = ym
    return RuleEngine().evaluate(db, year, month)
