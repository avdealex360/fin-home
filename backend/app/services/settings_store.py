from sqlalchemy.orm import Session

from app.models import Setting


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()


SECRET_PREFIX = "secret."


def get_secret(db: Session, key: str, default: str = "") -> str:
    return get_setting(db, key, default)


def set_secret(db: Session, key: str, value: str) -> None:
    # Empty input means "leave the stored secret unchanged".
    if value:
        set_setting(db, key, value)


def secret_is_set(db: Session, key: str) -> bool:
    return bool(get_setting(db, key, ""))


def mask_secret(value: str) -> str:
    if not value:
        return ""
    return "••••" + value[-4:]
