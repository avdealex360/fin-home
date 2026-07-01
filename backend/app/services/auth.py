from __future__ import annotations

import hashlib
import hmac
import time

from app.config import get_settings

SESSION_COOKIE = "fh_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 90  # 90 days — personal PWA, stay logged in


def _sign(payload: str) -> str:
    secret = get_settings().app_secret.encode()
    return hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()


def create_session_token() -> str:
    payload = str(int(time.time()))
    return f"{payload}.{_sign(payload)}"


def is_valid_session(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    payload, _, sig = token.partition(".")
    if not hmac.compare_digest(_sign(payload), sig):
        return False
    try:
        issued = int(payload)
    except ValueError:
        return False
    return (time.time() - issued) < SESSION_MAX_AGE


def verify_password(plain: str) -> bool:
    import bcrypt

    stored_hash = get_settings().app_password_hash
    if not stored_hash:
        return False
    try:
        return bcrypt.checkpw(plain.encode(), stored_hash.encode())
    except ValueError:
        return False
