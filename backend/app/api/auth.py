from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account, Invite, Workspace
from app.seed import ensure_workspace_settings
from app.services.auth import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    create_session_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str


class RegisterBody(BaseModel):
    token: str
    username: str
    password: str
    workspace_name: str | None = None


def _set_session(response: Response, request: Request, account_id: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(account_id),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response, db: Session = Depends(get_db)):
    account = (
        db.query(Account)
        .filter(
            func.lower(Account.username) == body.username.strip().lower(),
            Account.is_active.is_(True),
        )
        .first()
    )
    if not account or not verify_password(body.password, account.password_hash):
        raise HTTPException(401, "Неверный логин или пароль")
    _set_session(response, request, account.id)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    account_id = getattr(request.state, "account_id", None)
    if account_id is None:
        return {"authenticated": False}
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "username": account.username,
        "is_admin": account.is_admin,
        "workspace": {"id": account.workspace_id, "name": account.workspace.name},
    }


def _valid_invite(db: Session, token: str) -> Invite | None:
    invite = db.query(Invite).filter(Invite.token == token).first()
    if not invite or invite.used_at is not None:
        return None
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        return None
    return invite


@router.get("/invite/{token}")
def invite_info(token: str, db: Session = Depends(get_db)):
    invite = _valid_invite(db, token)
    if not invite:
        raise HTTPException(404, "Инвайт не найден или уже использован")
    return {
        "valid": True,
        "mode": "join" if invite.workspace_id else "create",
        "workspace_name": invite.workspace.name if invite.workspace else None,
    }


@router.post("/register")
def register(body: RegisterBody, request: Request, response: Response, db: Session = Depends(get_db)):
    invite = _valid_invite(db, body.token)
    if not invite:
        raise HTTPException(400, "Инвайт не найден или уже использован")

    username = body.username.strip()
    if len(username) < 3:
        raise HTTPException(400, "Логин должен быть не короче 3 символов")
    if len(body.password) < 8:
        raise HTTPException(400, "Пароль должен быть не короче 8 символов")
    # Case-insensitive: «Vasya» and «vasya» are the same login.
    if db.query(Account).filter(func.lower(Account.username) == username.lower()).first():
        raise HTTPException(400, "Такой логин уже занят")

    if invite.workspace_id:
        workspace = invite.workspace
    else:
        workspace = Workspace(name=(body.workspace_name or "").strip() or f"Бюджет {username}")
        db.add(workspace)
        db.flush()
        ensure_workspace_settings(db, workspace.id)

    account = Account(
        username=username,
        password_hash=hash_password(body.password),
        workspace_id=workspace.id,
    )
    db.add(account)
    db.flush()
    invite.used_at = datetime.utcnow()
    invite.used_by_account_id = account.id
    db.commit()

    _set_session(response, request, account.id)
    return {"ok": True, "workspace": {"id": workspace.id, "name": workspace.name}}
