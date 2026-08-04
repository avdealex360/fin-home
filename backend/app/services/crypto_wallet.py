"""Кошелёк USDC (ERC-20): баланс через Etherscan + уведомление «зарплата пришла».

Личная фича на один адрес в workspace. Фоновый воркер раз в 5 минут тянет баланс
USDC, кладёт его в кэш (`Setting`) и — не чаще одного раза в календарный месяц —
пишет в Telegram, когда баланс перевалил за заданный порог. На бюджет фича не
влияет: реестр операций она не трогает, доход всё равно записывается руками или ботом.

Ключи настроек (в пределах workspace):
    wallet_address          — адрес 0x… в Ethereum mainnet
    wallet_threshold        — порог уведомления, USDC
    wallet_notify_user_id   — кому писать; пусто = всем привязанным к Telegram
Состояние кэша (тот же workspace):
    wallet.balance, wallet.checked_at, wallet.error, wallet.alert_month
Ключ Etherscan — install-wide секрет `secret.etherscan_api_key` (как токен бота).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy.orm import Session

from app.models import AppUser, Setting
from app.services.settings_store import get_secret, get_setting, set_secret, set_setting
from app.services.tg_client import send_message

log = logging.getLogger("crypto_wallet")

# Etherscan V2 — один endpoint на все сети, chainid=1 это Ethereum mainnet.
_API = "https://api.etherscan.io/v2/api"
_CHAIN_ID = 1
USDC_CONTRACT = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
USDC_DECIMALS = 6
_TIMEOUT = 20.0

POLL_INTERVAL_SECONDS = 300  # 5 минут
_FIRST_POLL_DELAY_SECONDS = 20  # чтобы к первому открытию приложения баланс уже был

_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


class WalletError(Exception):
    """Ошибка настройки или ответа Etherscan — текст уходит прямо в UI."""


@dataclass
class WalletStatus:
    """То, что видит фронт: кэш и флаги настроек, без сырых секретов."""

    configured: bool
    address: str  # маска 0x1234…cdef
    address_set: bool
    api_key_set: bool
    threshold: Decimal
    notify_user_id: int | None
    balance: Decimal | None
    checked_at: str
    error: str
    alert_month: str


def mask_address(address: str) -> str:
    return f"{address[:6]}…{address[-4:]}" if address else ""


def normalize_address(raw: str) -> str:
    """Пустая строка = «выключить фичу», иначе адрес обязан быть валидным."""
    address = (raw or "").strip()
    if not address:
        return ""
    if not _ADDRESS_RE.match(address):
        raise WalletError("Адрес кошелька: ожидается 0x и 40 hex-символов")
    return address


def parse_amount(raw: str | None) -> Decimal:
    """«12 500,50» → Decimal('12500.50'). Пустое значение = 0 (порог выключен)."""
    text = re.sub(r"[\s\u00a0]", "", raw or "").replace(",", ".")
    if not text:
        return Decimal("0")
    try:
        value = Decimal(text)
    except InvalidOperation as e:
        raise WalletError("Порог должен быть числом") from e
    if value < 0:
        raise WalletError("Порог не может быть отрицательным")
    return value


def _cached_decimal(db: Session, ws: int, key: str) -> Decimal | None:
    raw = get_setting(db, ws, key, "")
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def status(db: Session, ws: int) -> WalletStatus:
    """Статус из кэша — без обращения к Etherscan."""
    address = get_setting(db, ws, "wallet_address", "")
    api_key_set = bool(get_secret(db, "secret.etherscan_api_key"))
    notify_raw = get_setting(db, ws, "wallet_notify_user_id", "")
    return WalletStatus(
        configured=bool(address) and api_key_set,
        address=mask_address(address),
        address_set=bool(address),
        api_key_set=api_key_set,
        threshold=parse_amount(get_setting(db, ws, "wallet_threshold", "0")),
        notify_user_id=int(notify_raw) if notify_raw.isdigit() else None,
        balance=_cached_decimal(db, ws, "wallet.balance"),
        checked_at=get_setting(db, ws, "wallet.checked_at", ""),
        error=get_setting(db, ws, "wallet.error", ""),
        alert_month=get_setting(db, ws, "wallet.alert_month", ""),
    )


def save_config(
    db: Session,
    ws: int,
    *,
    address: str | None = None,
    api_key: str | None = None,
    threshold: str | None = None,
    notify_user_id: int | None = None,
) -> WalletStatus:
    """None = «не трогать». Для адреса и порога пустая строка = сбросить."""
    if address is not None:
        set_setting(db, ws, "wallet_address", normalize_address(address))
    # Пустой ключ = оставить сохранённый (set_secret игнорирует пустое значение).
    if api_key is not None:
        set_secret(db, "secret.etherscan_api_key", api_key.strip())
    if threshold is not None:
        set_setting(db, ws, "wallet_threshold", str(parse_amount(threshold)))
    if notify_user_id is not None:
        # 0 = «всем, кто привязан к Telegram».
        set_setting(db, ws, "wallet_notify_user_id", str(notify_user_id) if notify_user_id else "")
    return status(db, ws)


def fetch_balance(address: str, api_key: str) -> Decimal:
    """Баланс USDC на адресе. Бросает WalletError на любой сбой."""
    params = {
        "chainid": _CHAIN_ID,
        "module": "account",
        "action": "tokenbalance",
        "contractaddress": USDC_CONTRACT,
        "address": address,
        "tag": "latest",
        "apikey": api_key,
    }
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(_API, params=params)
        data = resp.json()
    except httpx.HTTPError as e:
        raise WalletError(f"Etherscan недоступен: {e}") from e
    except ValueError as e:  # не JSON — обычно страница с ошибкой
        raise WalletError("Etherscan ответил не-JSON") from e
    if str(data.get("status")) != "1":
        raise WalletError(str(data.get("result") or data.get("message") or "Etherscan вернул ошибку"))
    raw = str(data.get("result", "0"))
    try:
        return Decimal(raw) / Decimal(10**USDC_DECIMALS)
    except InvalidOperation as e:
        raise WalletError(f"Не понял ответ Etherscan: {raw[:80]}") from e


def _fmt(value: Decimal) -> str:
    # Русский формат: пробел между тысячами, запятая как разделитель дробной части.
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def _notify_targets(db: Session, ws: int) -> list[str]:
    q = db.query(AppUser).filter(
        AppUser.workspace_id == ws,
        AppUser.telegram_id.isnot(None),
        AppUser.telegram_id != "",
    )
    chosen = get_setting(db, ws, "wallet_notify_user_id", "")
    if chosen.isdigit():
        q = q.filter(AppUser.id == int(chosen))
    return [u.telegram_id for u in q.all() if u.telegram_id]


def _alert_text(balance: Decimal, previous: Decimal | None, threshold: Decimal) -> str:
    lines = ["💰 <b>Кошелёк USDC пополнен</b>", f"Баланс: <b>{_fmt(balance)} USDC</b>"]
    if previous is not None and balance > previous:
        lines.append(f"Пришло: +{_fmt(balance - previous)} USDC")
    lines.append(f"Порог: {_fmt(threshold)} USDC")
    lines.append("Похоже, зарплата пришла — не забудь записать доход в бюджет.")
    return "\n".join(lines)


def _maybe_notify(
    db: Session, ws: int, balance: Decimal, previous: Decimal | None, now: datetime
) -> bool:
    threshold = parse_amount(get_setting(db, ws, "wallet_threshold", "0"))
    if threshold <= 0 or balance < threshold:
        return False
    month = now.strftime("%Y-%m")
    # Одно уведомление на календарный месяц: баланс висит выше порога днями,
    # а долбить в Telegram каждые 5 минут незачем.
    if get_setting(db, ws, "wallet.alert_month", "") == month:
        return False
    token = get_secret(db, "secret.tg_bot_token")
    targets = _notify_targets(db, ws)
    if not token or not targets:
        log.warning("wallet alert skipped (ws=%s): no bot token or no linked telegram user", ws)
        return False
    text = _alert_text(balance, previous, threshold)
    for chat_id in targets:
        send_message(token, chat_id, text)
    set_setting(db, ws, "wallet.alert_month", month)
    return True


def check(db: Session, ws: int, *, now: datetime | None = None, notify: bool = True) -> WalletStatus:
    """Тянет баланс, обновляет кэш и при необходимости шлёт уведомление."""
    address = get_setting(db, ws, "wallet_address", "")
    api_key = get_secret(db, "secret.etherscan_api_key")
    if not address or not api_key:
        return status(db, ws)
    now = now or datetime.now()
    stamp = now.isoformat(timespec="seconds")
    try:
        balance = fetch_balance(address, api_key)
    except WalletError as e:
        # Ошибку показываем в UI, но кэш баланса не стираем — старое число лучше пустоты.
        set_setting(db, ws, "wallet.error", str(e)[:200])
        set_setting(db, ws, "wallet.checked_at", stamp)
        log.warning("wallet check failed (ws=%s): %s", ws, e)
        return status(db, ws)
    previous = _cached_decimal(db, ws, "wallet.balance")
    set_setting(db, ws, "wallet.balance", str(balance))
    set_setting(db, ws, "wallet.checked_at", stamp)
    set_setting(db, ws, "wallet.error", "")
    if notify:
        _maybe_notify(db, ws, balance, previous, now)
    return status(db, ws)


def workspaces_with_wallet(db: Session) -> list[int]:
    rows = (
        db.query(Setting.workspace_id)
        .filter(Setting.key == "wallet_address", Setting.value != "")
        .all()
    )
    return [row[0] for row in rows if row[0] is not None]


def check_all(db: Session, *, now: datetime | None = None) -> int:
    checked = 0
    for ws in workspaces_with_wallet(db):
        check(db, ws, now=now)
        checked += 1
    return checked


def _check_all_sync(session_factory) -> int:
    db = session_factory()
    try:
        return check_all(db)
    finally:
        db.close()


async def poll_loop(session_factory, interval: int = POLL_INTERVAL_SECONDS) -> None:
    """Фоновый воркер опроса кошельков.

    Uvicorn поднимается одним воркером (см. CMD в Dockerfile), поэтому одна
    задача на процесс = один опрос на инсталляцию. httpx и SQLAlchemy тут
    синхронные, так что итерация уходит в поток и не блокирует event loop.
    """
    await asyncio.sleep(_FIRST_POLL_DELAY_SECONDS)
    while True:
        try:
            await asyncio.to_thread(_check_all_sync, session_factory)
        except asyncio.CancelledError:
            raise
        except Exception:  # воркер не имеет права умирать
            log.exception("wallet poll iteration failed")
        await asyncio.sleep(interval)
