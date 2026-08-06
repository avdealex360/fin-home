"""MOEX ISS quotes for the invest section — keyless public API.

One request per board (blue-chip shares, ETFs, indices) regardless of
watchlist size; results are merged and cached in memory for _TTL seconds
so page reloads don't hammer iss.moex.com.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

_BASE = "https://iss.moex.com/iss"
# (market, board): TQBR — shares, TQTF — ETFs/funds, SNDX — indices.
_BOARDS = [("shares", "TQBR"), ("shares", "TQTF"), ("index", "SNDX")]
_TIMEOUT = 15.0
_TTL = 600.0
_CACHE: dict[tuple[str, ...], tuple[float, dict[str, "Quote"]]] = {}


def _client_factory() -> httpx.Client:
    return httpx.Client(timeout=_TIMEOUT)


class MoexError(Exception):
    pass


@dataclass
class Quote:
    ticker: str
    name: str
    price: float | None
    change_pct: float | None


def _rows(block: dict) -> list[dict]:
    cols = block.get("columns") or []
    return [dict(zip(cols, row)) for row in block.get("data") or []]


def _first(row: dict, *keys):
    for k in keys:
        if row.get(k) is not None:
            return row[k]
    return None


def get_quotes(tickers: list[str]) -> list[Quote]:
    key = tuple(sorted(tickers))
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL:
        found = hit[1]
        return [found[t] for t in tickers if t in found]

    wanted = set(tickers)
    found: dict[str, Quote] = {}
    try:
        with _client_factory() as client:
            for market, board in _BOARDS:
                resp = client.get(
                    f"{_BASE}/engines/stock/markets/{market}/boards/{board}/securities.json",
                    params={
                        "iss.meta": "off",
                        "iss.only": "securities,marketdata",
                        "securities": ",".join(tickers),
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
                sec = {r.get("SECID"): r for r in _rows(payload.get("securities", {}))}
                for md in _rows(payload.get("marketdata", {})):
                    t = md.get("SECID")
                    if t not in wanted or t in found:
                        continue
                    s = sec.get(t, {})
                    price = _first(md, "LAST", "CURRENTVALUE")
                    if price is None:
                        price = _first(s, "PREVPRICE", "PREVADMITTEDQUOTE")
                    chg = _first(md, "LASTTOPREVPRICE", "LASTCHANGEPRC")
                    found[t] = Quote(
                        ticker=t,
                        name=s.get("SHORTNAME") or t,
                        price=float(price) if price is not None else None,
                        change_pct=float(chg) if chg is not None else None,
                    )
    except httpx.HTTPError as e:
        raise MoexError(f"moex: {e}") from e

    _CACHE[key] = (now, found)
    return [found[t] for t in tickers if t in found]
