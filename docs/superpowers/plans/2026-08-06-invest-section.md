# Investments Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reference section `#/invest` — beginner knowledge base, live MOEX market widget with per-workspace watchlist, daily AI market overview.

**Architecture:** Backend gets a keyless MOEX ISS client (`services/moex.py`, in-memory 10-min cache), a thin `api/invest.py` router (market / watchlist / overview) and a day-cached AI overview builder reusing `ai/router.py`. Frontend gets `routes/Invest.svelte` (static knowledge cards + market list + overview block) linked from More. No DB migrations — watchlist and overview cache live in `Setting`.

**Tech Stack:** FastAPI, httpx, SQLAlchemy `Setting`, Svelte 5, MOEX ISS JSON API.

## Global Constraints

- No new DB tables/migrations; per-workspace state via `Setting` (`invest.*` keys).
- Section is reference-only: no effect on budget/50-30-20.
- AI overview must carry the disclaimer «Не является индивидуальной инвестиционной рекомендацией».
- Follow existing patterns: services without FastAPI imports; thin api files; tests mirror `tests/test_crypto_wallet.py` style (httpx.MockTransport, monkeypatched client factory).

---

### Task 1: MOEX ISS client

**Files:**
- Create: `backend/app/services/moex.py`
- Test: `backend/tests/test_moex.py`

**Interfaces:**
- Produces: `Quote` dataclass `(ticker: str, name: str, price: float | None, change_pct: float | None)`; `get_quotes(tickers: list[str]) -> list[Quote]` (raises `MoexError` on total failure); `_client_factory` hook for tests; module cache `_CACHE` with `_TTL = 600`.

- [ ] Write failing tests: parse shares (TQBR), ETF (TQTF) and index (SNDX) rows from mocked ISS JSON; missing ticker silently absent; network error raises `MoexError`; second call within TTL served from cache (handler counts requests).
- [ ] Run: `.venv/bin/python -m pytest tests/test_moex.py -q` → FAIL (module missing).
- [ ] Implement `moex.py`: one request per board — `iss.moex.com/iss/engines/stock/markets/{shares|index}/boards/{TQBR,TQTF,SNDX}/securities.json?iss.meta=off&iss.only=securities,marketdata&securities={csv}`; map columns by name (`SECID`, `SHORTNAME`, `LAST`/`CURRENTVALUE`, `LASTTOPREVPRICE`/`LASTCHANGEPRC`, fallback price `PREVPRICE`/`PREVADMITTEDQUOTE`); merge, preserve watchlist order; time-based cache keyed by sorted tickers.
- [ ] Run tests → PASS; full suite green.
- [ ] Commit `feat: MOEX ISS quotes client with in-memory cache`.

### Task 2: invest API (market + watchlist)

**Files:**
- Create: `backend/app/api/invest.py`
- Modify: `backend/app/main.py` (include router, same pattern as `api/wallet.py`)
- Test: `backend/tests/test_invest_api.py`

**Interfaces:**
- Consumes: `moex.get_quotes`, `settings_store.get_setting/set_setting`, `api/deps.py` workspace helper (same as wallet endpoints).
- Produces: `GET /api/invest/market` → `{"quotes": [{ticker,name,price,change_pct}], "error": null}`; `GET /api/invest/watchlist` → `{"tickers": [...]}` (default `IMOEX,SBER,SBMX,LQDT` persisted on first read); `PUT /api/invest/watchlist` body `{"tickers": [...]}` (validate `^[A-Z0-9]{1,12}$`, 1..20 items, uppercase, 422 otherwise).

- [ ] Write failing tests: default watchlist created on first GET; PUT stores and normalizes case; PUT rejects bad ticker/empty list; market endpoint returns quotes (moex monkeypatched) and `{"error": ...}` degradation when `get_quotes` raises `MoexError`; endpoints are workspace-scoped (two workspaces see different watchlists).
- [ ] Run → FAIL. Implement router. Run → PASS; suite green.
- [ ] Commit `feat: invest API — market quotes and per-workspace watchlist`.

### Task 3: AI market overview

**Files:**
- Create: `backend/app/services/invest_overview.py`
- Modify: `backend/app/api/invest.py` (add `GET /api/invest/overview`)
- Test: `backend/tests/test_invest_overview.py`

**Interfaces:**
- Consumes: `moex.get_quotes`, AI completion entry point used by `services/daily_digest.py` (inspect and reuse the same router call), `settings_store`.
- Produces: `get_or_build(db, ws_id) -> dict` → `{"text": str | None, "date": "YYYY-MM-DD", "configured": bool}`; cache keys `invest.overview`, `invest.overview_date` (per workspace); endpoint returns the dict as-is.

- [ ] Write failing tests: builds text via monkeypatched AI call and caches for the calendar day (AI called once across two invocations); stale date rebuilds; missing AI keys → `configured: false`, no AI call; AI failure → cached=None but no exception.
- [ ] Run → FAIL. Implement: prompt = beginner-friendly explanation of today's watchlist moves + index, explicit "no buy/sell advice" instruction; append disclaimer server-side. Run → PASS; suite green.
- [ ] Commit `feat: day-cached AI market overview for invest section`.

### Task 4: frontend — Invest page

**Files:**
- Modify: `frontend/src/lib/api.ts` (types `Quote`, `InvestMarket`, `InvestOverview` + `getInvestMarket/getInvestWatchlist/putInvestWatchlist/getInvestOverview`)
- Create: `frontend/src/routes/Invest.svelte`
- Modify: `frontend/src/App.svelte` (route `#/invest`), `frontend/src/routes/More.svelte` (link «Инвестиции», icon `ti-chart-line` — verify glyph exists in Tabler 3.24.0 CSS)

**Interfaces:**
- Consumes: Task 2/3 endpoints verbatim.
- Produces: page with three cards — «Рынок сегодня» (quotes list, green/red change, watchlist editor: add input + remove ×), «AI-обзор» (text or hint to Интеграции; disclaimer footer), «База знаний» (static accordion: ИИС-3 и вычеты; классы активов; диверсификация; типовые портфели новичка; типичные ошибки; фонды Сбера SBMX/SBGB/LQDT). Content written in Russian at implementation, reviewed via FAQ-style cards.

- [ ] Implement page + routing + More link following `Wallet.svelte`/`Faq.svelte` patterns; loading/error states for market block.
- [ ] `npm run build` → clean.
- [ ] Commit `feat: invest section UI — knowledge base, market watchlist, AI overview`.

### Task 5: docs + ship

**Files:**
- Modify: `frontend/src/routes/Faq.svelte` (card «Инвестиции: база знаний и рынок»), `CLAUDE.md` (new subsection), `docs/superpowers/plans/…` (check boxes)

- [ ] FAQ card + CLAUDE.md subsection (services, endpoints, Setting keys, no-ledger note).
- [ ] Full backend suite + frontend build green.
- [ ] Commit `docs: invest section notes in FAQ and CLAUDE.md`, push `origin main`.
