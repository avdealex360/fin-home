from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.config import get_settings
from app.services.auth import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    create_session_token,
    is_valid_session,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response):
    settings = get_settings()
    if body.username != settings.app_user or not verify_password(body.password):
        raise HTTPException(401, "Неверный логин или пароль")
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    return {"authenticated": is_valid_session(request.cookies.get(SESSION_COOKIE))}
