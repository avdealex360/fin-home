"""Admin panel API: workspaces overview, invites, accounts. is_admin only."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db import get_db
from app.models import Account, Invite, Transaction, Workspace
from app.services.auth import hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    tx_counts = dict(
        db.query(Transaction.workspace_id, func.count(Transaction.id))
        .group_by(Transaction.workspace_id)
        .all()
    )
    accounts = db.query(Account).order_by(Account.id).all()
    by_ws: dict[int, list[Account]] = {}
    for a in accounts:
        by_ws.setdefault(a.workspace_id, []).append(a)
    workspaces = db.query(Workspace).order_by(Workspace.id).all()
    return {
        "workspaces": [
            {
                "id": w.id,
                "name": w.name,
                "onboarded": w.onboarded,
                "created_at": w.created_at.isoformat() if w.created_at else None,
                "tx_count": tx_counts.get(w.id, 0),
                "accounts": [
                    {
                        "id": a.id,
                        "username": a.username,
                        "is_admin": a.is_admin,
                        "is_active": a.is_active,
                        "created_at": a.created_at.isoformat() if a.created_at else None,
                    }
                    for a in by_ws.get(w.id, [])
                ],
            }
            for w in workspaces
        ]
    }


# ---- invites ----
class InviteBody(BaseModel):
    label: str | None = None
    workspace_id: int | None = None  # join this workspace; None = fresh workspace
    ttl_days: int | None = None


def _invite_dict(i: Invite) -> dict:
    return {
        "id": i.id,
        "token": i.token,
        "label": i.label,
        "workspace_id": i.workspace_id,
        "workspace_name": i.workspace.name if i.workspace else None,
        "expires_at": i.expires_at.isoformat() if i.expires_at else None,
        "used_at": i.used_at.isoformat() if i.used_at else None,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


@router.get("/invites")
def list_invites(db: Session = Depends(get_db)):
    invites = db.query(Invite).order_by(Invite.id.desc()).all()
    return [_invite_dict(i) for i in invites]


@router.post("/invites")
def create_invite(body: InviteBody, db: Session = Depends(get_db)):
    if body.workspace_id is not None:
        if not db.query(Workspace).filter(Workspace.id == body.workspace_id).first():
            raise HTTPException(404, "workspace not found")
    invite = Invite(
        token=secrets.token_urlsafe(24),
        label=(body.label or "").strip() or None,
        workspace_id=body.workspace_id,
        expires_at=datetime.utcnow() + timedelta(days=body.ttl_days) if body.ttl_days else None,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return _invite_dict(invite)


@router.delete("/invites/{invite_id}")
def revoke_invite(invite_id: int, db: Session = Depends(get_db)):
    invite = db.query(Invite).filter(Invite.id == invite_id).first()
    if invite and invite.used_at is None:
        db.delete(invite)
        db.commit()
    return {"ok": True}


# ---- accounts ----
class AccountPatchBody(BaseModel):
    is_active: bool | None = None
    password: str | None = None


@router.patch("/accounts/{account_id}")
def patch_account(
    account_id: int,
    body: AccountPatchBody,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(404, "account not found")
    if body.is_active is not None:
        if account.id == admin_id and not body.is_active:
            raise HTTPException(400, "нельзя деактивировать собственный аккаунт")
        account.is_active = body.is_active
    if body.password:
        if len(body.password) < 8:
            raise HTTPException(400, "Пароль должен быть не короче 8 символов")
        account.password_hash = hash_password(body.password)
    db.commit()
    return {"ok": True}
