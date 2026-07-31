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


def create_session_token(account_id: int) -> str:
    payload = f"{account_id}.{int(time.time())}"
    return f"{payload}.{_sign(payload)}"


def session_account_id(token: str | None) -> int | None:
    """Return the account id from a valid session token, else None."""
    if not token or token.count(".") != 2:
        return None
    account_part, ts_part, sig = token.split(".")
    payload = f"{account_part}.{ts_part}"
    if not hmac.compare_digest(_sign(payload), sig):
        return None
    try:
        account_id = int(account_part)
        issued = int(ts_part)
    except ValueError:
        return None
    if (time.time() - issued) >= SESSION_MAX_AGE:
        return None
    return account_id


def hash_password(plain: str) -> str:
    import bcrypt

    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, stored_hash: str | None) -> bool:
    import bcrypt

    if not stored_hash:
        return False
    try:
        return bcrypt.checkpw(plain.encode(), stored_hash.encode())
    except ValueError:
        return False
