from sqlalchemy.orm import Session

from app.models import Setting


def _row(db: Session, ws_id: int | None, key: str) -> Setting | None:
    q = db.query(Setting).filter(Setting.key == key)
    if ws_id is None:
        q = q.filter(Setting.workspace_id.is_(None))
    else:
        q = q.filter(Setting.workspace_id == ws_id)
    return q.first()


def get_setting(db: Session, ws_id: int | None, key: str, default: str = "") -> str:
    row = _row(db, ws_id, key)
    return row.value if row else default


def set_setting(db: Session, ws_id: int | None, key: str, value: str) -> None:
    row = _row(db, ws_id, key)
    if row:
        row.value = value
    else:
        db.add(Setting(workspace_id=ws_id, key=key, value=value))
    db.commit()


SECRET_PREFIX = "secret."


# Secrets are install-wide (workspace_id NULL): one Telegram bot / AI account.
def get_secret(db: Session, key: str, default: str = "") -> str:
    return get_setting(db, None, key, default)


def set_secret(db: Session, key: str, value: str) -> None:
    # Empty input means "leave the stored secret unchanged".
    if value:
        set_setting(db, None, key, value)


def secret_is_set(db: Session, key: str) -> bool:
    return bool(get_setting(db, None, key, ""))


def mask_secret(value: str) -> str:
    if not value:
        return ""
    return "••••" + value[-4:]
