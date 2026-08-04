"""Кошелёк USDC: парсинг ответа Etherscan, порог и правило «одно письмо в месяц»."""

from datetime import datetime
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — регистрирует модели в Base.metadata
from app.db import Base
from app.models import AppUser
from app.services import crypto_wallet as cw
from app.services.settings_store import get_setting, set_secret, set_setting
from tests.conftest import create_workspace

ADDRESS = "0x5564Cfa0b6290b4acdFe154Efe5c4d4aF0713148"


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'wallet.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def ws(db):
    return create_workspace(db).id


def _configure(db, ws, *, threshold="1000", tg_id="777"):
    set_setting(db, ws, "wallet_address", ADDRESS)
    set_setting(db, ws, "wallet_threshold", threshold)
    set_secret(db, "secret.etherscan_api_key", "key")
    set_secret(db, "secret.tg_bot_token", "token")
    if tg_id:
        db.add(AppUser(workspace_id=ws, name="Я", telegram_id=tg_id))
        db.commit()


def _stub_fetch(monkeypatch, value: str):
    monkeypatch.setattr(cw, "fetch_balance", lambda address, api_key: Decimal(value))


def _capture_sends(monkeypatch) -> list[tuple]:
    sent: list[tuple] = []
    monkeypatch.setattr(cw, "send_message", lambda token, chat, text: sent.append((chat, text)))
    return sent


# --- разбор ответов Etherscan --------------------------------------------------


def _stub_transport(monkeypatch, payload: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    original = httpx.Client

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr(cw.httpx, "Client", factory)


def test_fetch_balance_converts_6_decimals(monkeypatch):
    _stub_transport(monkeypatch, {"status": "1", "message": "OK", "result": "1234560000"})
    assert cw.fetch_balance(ADDRESS, "key") == Decimal("1234.56")


def test_fetch_balance_raises_on_api_error(monkeypatch):
    _stub_transport(monkeypatch, {"status": "0", "message": "NOTOK", "result": "Invalid API Key"})
    with pytest.raises(cw.WalletError, match="Invalid API Key"):
        cw.fetch_balance(ADDRESS, "key")


# --- валидация настроек -------------------------------------------------------


def test_normalize_address():
    assert cw.normalize_address(f"  {ADDRESS} ") == ADDRESS
    assert cw.normalize_address("") == ""
    with pytest.raises(cw.WalletError):
        cw.normalize_address("0xnope")


def test_parse_amount_accepts_russian_formatting():
    assert cw.parse_amount("12 500,50") == Decimal("12500.50")
    assert cw.parse_amount("") == Decimal("0")
    with pytest.raises(cw.WalletError):
        cw.parse_amount("много")


def test_status_masks_address_and_hides_key(db, ws):
    _configure(db, ws, tg_id="")
    s = cw.status(db, ws)
    assert s.configured is True
    assert s.address == "0x5564…3148"
    assert ADDRESS not in s.address
    assert s.api_key_set is True


def test_save_config_keeps_key_when_blank(db, ws):
    cw.save_config(db, ws, address=ADDRESS, api_key="secret-key", threshold="1000")
    cw.save_config(db, ws, api_key="")  # пустое поле = не трогать сохранённый ключ
    assert cw.get_api_key(db, ws) == "secret-key"
    assert cw.status(db, ws).threshold == Decimal("1000")


def test_api_key_is_per_workspace_with_install_wide_fallback(db, ws):
    other = create_workspace(db, name="Другая семья").id
    cw.save_config(db, ws, api_key="mine")
    # Ключ одного workspace не утекает в другой…
    assert cw.get_api_key(db, other) == ""
    # …но install-wide значение работает как общий запасной вариант.
    set_secret(db, "secret.etherscan_api_key", "shared")
    assert cw.get_api_key(db, other) == "shared"
    assert cw.get_api_key(db, ws) == "mine"  # свой ключ важнее общего


def test_save_config_empty_address_disables(db, ws):
    cw.save_config(db, ws, address=ADDRESS, api_key="k")
    assert cw.status(db, ws).configured is True
    cw.save_config(db, ws, address="")
    assert cw.status(db, ws).configured is False


# --- уведомления --------------------------------------------------------------


def test_notifies_once_per_month(db, ws, monkeypatch):
    _configure(db, ws)
    _stub_fetch(monkeypatch, "1500")
    sent = _capture_sends(monkeypatch)

    cw.check(db, ws, now=datetime(2026, 8, 4, 10, 0))
    assert len(sent) == 1
    assert "1 500,00 USDC" in sent[0][1]
    assert sent[0][0] == "777"

    # Баланс так и висит выше порога — повторно не пишем.
    cw.check(db, ws, now=datetime(2026, 8, 4, 10, 5))
    cw.check(db, ws, now=datetime(2026, 8, 31, 23, 0))
    assert len(sent) == 1

    # Новый календарный месяц — снова можно.
    cw.check(db, ws, now=datetime(2026, 9, 1, 9, 0))
    assert len(sent) == 2


def test_no_notification_below_threshold(db, ws, monkeypatch):
    _configure(db, ws, threshold="1000")
    _stub_fetch(monkeypatch, "999.99")
    sent = _capture_sends(monkeypatch)
    cw.check(db, ws, now=datetime(2026, 8, 4, 10, 0))
    assert sent == []
    assert cw.status(db, ws).balance == Decimal("999.99")


def test_zero_threshold_never_notifies(db, ws, monkeypatch):
    _configure(db, ws, threshold="0")
    _stub_fetch(monkeypatch, "50000")
    sent = _capture_sends(monkeypatch)
    cw.check(db, ws, now=datetime(2026, 8, 4, 10, 0))
    assert sent == []


def test_alert_reports_delta(db, ws, monkeypatch):
    _configure(db, ws)
    set_setting(db, ws, "wallet.balance", "200")
    _stub_fetch(monkeypatch, "1700")
    sent = _capture_sends(monkeypatch)
    cw.check(db, ws, now=datetime(2026, 8, 4, 10, 0))
    assert "+1 500,00 USDC" in sent[0][1]


def test_notify_user_id_narrows_recipients(db, ws, monkeypatch):
    _configure(db, ws)
    other = AppUser(workspace_id=ws, name="Жена", telegram_id="888")
    db.add(other)
    db.commit()
    cw.save_config(db, ws, notify_user_id=other.id)
    _stub_fetch(monkeypatch, "1500")
    sent = _capture_sends(monkeypatch)
    cw.check(db, ws, now=datetime(2026, 8, 4, 10, 0))
    assert [chat for chat, _ in sent] == ["888"]


def test_fetch_error_keeps_last_balance_and_records_error(db, ws, monkeypatch):
    _configure(db, ws)
    _stub_fetch(monkeypatch, "1500")
    _capture_sends(monkeypatch)
    cw.check(db, ws, now=datetime(2026, 8, 4, 10, 0))

    def boom(address, api_key):
        raise cw.WalletError("Max rate limit reached")

    monkeypatch.setattr(cw, "fetch_balance", boom)
    s = cw.check(db, ws, now=datetime(2026, 8, 4, 10, 5))
    assert s.balance == Decimal("1500")  # старое число лучше пустоты
    assert "rate limit" in s.error


def test_unconfigured_wallet_is_skipped(db, ws, monkeypatch):
    monkeypatch.setattr(cw, "fetch_balance", lambda *a: pytest.fail("не должен вызываться"))
    s = cw.check(db, ws)
    assert s.configured is False
    assert get_setting(db, ws, "wallet.checked_at", "") == ""


def test_check_all_covers_only_workspaces_with_address(db, monkeypatch):
    ws_with = create_workspace(db, name="С кошельком").id
    create_workspace(db, name="Без кошелька")
    _configure(db, ws_with, threshold="0")
    _stub_fetch(monkeypatch, "10")
    assert cw.workspaces_with_wallet(db) == [ws_with]
    assert cw.check_all(db) == 1


# --- API ----------------------------------------------------------------------


def test_wallet_endpoints(api, monkeypatch):
    _stub_fetch(monkeypatch, "2500")
    r = api.client.post("/api/wallet", json={
        "address": ADDRESS, "etherscan_api_key": "SUPER-SECRET-KEY",
        "threshold": "1 000", "notify_user_id": 0,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["configured"] is True
    assert body["address"] == "0x5564…3148"
    assert float(body["threshold"]) == 1000.0

    got = api.client.get("/api/wallet").json()
    assert got["balance"] is None  # ещё не опрашивали

    refreshed = api.client.post("/api/wallet/refresh").json()
    assert float(refreshed["balance"]) == 2500.0
    assert refreshed["error"] == ""

    # Ключ и полный адрес наружу не уходят.
    assert "SUPER-SECRET-KEY" not in r.text
    assert ADDRESS not in r.text


def test_wallet_rejects_bad_address(api):
    r = api.client.post("/api/wallet", json={"address": "0x123"})
    assert r.status_code == 400
    assert "hex" in r.json()["detail"]


def test_non_admin_can_configure_wallet(api):
    """Кошелёк — не админская настройка: жена в том же workspace тоже может."""
    from app.services.auth import SESSION_COOKIE, create_session_token

    from tests.conftest import create_account

    s = api.Session()
    member = create_account(s, api.ws_id, username="wife", is_admin=False)
    s.close()

    api.client.cookies.set(SESSION_COOKIE, create_session_token(member.id))
    r = api.client.post("/api/wallet", json={"address": ADDRESS, "threshold": "500"})
    assert r.status_code == 200, r.text
    assert r.json()["address_set"] is True
    assert api.client.get("/api/wallet").status_code == 200
    # А админские настройки бота по-прежнему закрыты.
    assert api.client.get("/api/settings/integrations").status_code == 403
