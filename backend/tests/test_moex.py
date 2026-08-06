"""MOEX ISS client: parsing boards, watchlist order, TTL cache, errors."""

import httpx
import pytest

from app.services import moex
from app.services.moex import MoexError


@pytest.fixture(autouse=True)
def clear_cache():
    moex._CACHE.clear()
    yield
    moex._CACHE.clear()


def _payload_for(path: str) -> dict:
    if "boards/TQBR" in path:
        return {
            "securities": {"columns": ["SECID", "SHORTNAME", "PREVPRICE"],
                           "data": [["SBER", "Сбербанк", 310.0]]},
            "marketdata": {"columns": ["SECID", "LAST", "LASTTOPREVPRICE"],
                           "data": [["SBER", 312.4, 0.85]]},
        }
    if "boards/TQTF" in path:
        return {
            "securities": {"columns": ["SECID", "SHORTNAME", "PREVPRICE"],
                           "data": [["SBMX", "СберИндекс", 32.1]]},
            "marketdata": {"columns": ["SECID", "LAST", "LASTTOPREVPRICE"],
                           "data": [["SBMX", None, None]]},
        }
    if "boards/SNDX" in path:
        return {
            "securities": {"columns": ["SECID", "SHORTNAME"],
                           "data": [["IMOEX", "Индекс МосБиржи"]]},
            "marketdata": {"columns": ["SECID", "CURRENTVALUE", "LASTCHANGEPRC"],
                           "data": [["IMOEX", 3214.5, 0.8]]},
        }
    return {"securities": {"columns": [], "data": []},
            "marketdata": {"columns": [], "data": []}}


def _mock(monkeypatch, counter=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if counter is not None:
            counter.append(request.url.path)
        return httpx.Response(200, json=_payload_for(request.url.path))
    monkeypatch.setattr(moex, "_client_factory",
                        lambda: httpx.Client(transport=httpx.MockTransport(handler)))


def test_parses_share_etf_and_index(monkeypatch):
    _mock(monkeypatch)
    quotes = moex.get_quotes(["IMOEX", "SBER", "SBMX"])
    by_t = {q.ticker: q for q in quotes}
    assert by_t["SBER"].price == 312.4
    assert by_t["SBER"].change_pct == 0.85
    assert by_t["SBER"].name == "Сбербанк"
    assert by_t["IMOEX"].price == 3214.5
    assert by_t["IMOEX"].change_pct == 0.8
    # ETF without a trade yet falls back to PREVPRICE, change unknown
    assert by_t["SBMX"].price == 32.1
    assert by_t["SBMX"].change_pct is None


def test_preserves_watchlist_order_and_skips_unknown(monkeypatch):
    _mock(monkeypatch)
    quotes = moex.get_quotes(["IMOEX", "NOSUCH", "SBER"])
    assert [q.ticker for q in quotes] == ["IMOEX", "SBER"]


def test_second_call_within_ttl_uses_cache(monkeypatch):
    calls: list[str] = []
    _mock(monkeypatch, calls)
    moex.get_quotes(["SBER"])
    n = len(calls)
    moex.get_quotes(["SBER"])
    assert len(calls) == n  # no extra HTTP traffic


def test_network_error_raises_moex_error(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("boom")
    monkeypatch.setattr(moex, "_client_factory",
                        lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MoexError):
        moex.get_quotes(["SBER"])
