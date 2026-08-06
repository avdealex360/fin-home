"""Invest API: watchlist defaults/validation, market quotes, degradation."""

from app.api import invest as invest_api
from app.services.moex import MoexError, Quote


def test_watchlist_default_created_on_first_get(api):
    r = api.client.get("/api/invest/watchlist")
    assert r.status_code == 200
    assert r.json()["tickers"] == ["IMOEX", "SBER", "SBMX", "LQDT"]


def test_watchlist_put_normalizes_and_persists(api):
    r = api.client.put("/api/invest/watchlist", json={"tickers": ["sber", "LQDT"]})
    assert r.status_code == 200
    assert api.client.get("/api/invest/watchlist").json()["tickers"] == ["SBER", "LQDT"]


def test_watchlist_put_rejects_garbage(api):
    assert api.client.put("/api/invest/watchlist", json={"tickers": []}).status_code == 422
    assert api.client.put("/api/invest/watchlist",
                          json={"tickers": ["OK", "not a ticker!"]}).status_code == 422
    assert api.client.put("/api/invest/watchlist",
                          json={"tickers": ["A" * 13]}).status_code == 422


def test_market_returns_quotes_for_watchlist(api, monkeypatch):
    seen = {}

    def fake_quotes(tickers):
        seen["tickers"] = tickers
        return [Quote("SBER", "Сбербанк", 312.4, 0.85)]
    monkeypatch.setattr(invest_api, "get_quotes", fake_quotes)

    api.client.put("/api/invest/watchlist", json={"tickers": ["SBER"]})
    r = api.client.get("/api/invest/market")
    assert r.status_code == 200
    body = r.json()
    assert body["error"] is None
    assert body["quotes"] == [
        {"ticker": "SBER", "name": "Сбербанк", "price": 312.4, "change_pct": 0.85}
    ]
    assert seen["tickers"] == ["SBER"]


def test_watchlist_is_workspace_scoped(api):
    from app.services.auth import SESSION_COOKIE, create_session_token
    from tests.conftest import create_account, create_workspace

    api.client.put("/api/invest/watchlist", json={"tickers": ["LKOH"]})

    s = api.Session()
    other_ws = create_workspace(s, name="Другая")
    other = create_account(s, other_ws.id, username="other")
    s.close()

    api.client.cookies.set(SESSION_COOKIE, create_session_token(other.id))
    r = api.client.get("/api/invest/watchlist")
    assert r.json()["tickers"] == ["IMOEX", "SBER", "SBMX", "LQDT"]


def test_market_degrades_when_moex_down(api, monkeypatch):
    def boom(tickers):
        raise MoexError("connect timeout")
    monkeypatch.setattr(invest_api, "get_quotes", boom)
    r = api.client.get("/api/invest/market")
    assert r.status_code == 200
    body = r.json()
    assert body["quotes"] == []
    assert body["error"]
