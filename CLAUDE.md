# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A personal family budget web app (Russian UI) implementing the **50/30/20 rule**. Runs on a VPS behind Caddy. Mobile-first, self-hosted, installable as a PWA.

**Stack:** Svelte 5 + Vite (PWA SPA) · Python 3.12 · FastAPI (JSON API) · SQLite · SQLAlchemy 2.x · Alembic · Chart.js · Docker · Caddy

> **v3 (June 2026):** rewritten from the original HTMX/Jinja2 app into a Svelte SPA + JSON API split. The frontend is a single-page app served as static files; the backend speaks JSON only. Auth is app-level: a login screen posts to `/api/auth/login`, which sets a signed httponly session cookie (`app/services/auth.py`); a middleware in `main.py` gates all `/api/*` except `/api/auth/*`, `/api/health`, and docs.

> **v4 (July 2026): multi-tenancy.** `Account` (login: username + bcrypt, `is_admin`) belongs to a `Workspace`; every root entity (`AppUser`, `Category`, `Transaction`, `SinkingFund`, `Debt`, `MonthlyPlan`) carries `workspace_id`, and every endpoint/service filters by it (`deps.ws_id` reads `request.state`, filled by the auth middleware from the session cookie `{account_id}.{ts}.{hmac}`). `Setting` is `(workspace_id, key)`; `workspace_id NULL` = install-wide scope (`secret.*` keys, AI/bot toggles — one bot for all workspaces, routed by `AppUser.telegram_id` which stays globally unique). Registration is invite-only (`Invite`: single-use token; bound to a workspace = join it, unbound = a fresh workspace is created). Admin API `/api/admin/*` + UI `#/admin` (invites, accounts, workspaces overview). On first start `seed.ensure_admin_account` bootstraps the admin from `APP_USER`/`APP_PASSWORD_HASH` (or plain `APP_PASSWORD` in dev). `AppUser` remains a per-workspace payer label, not a login.

## Repo layout

```
backend/          — FastAPI JSON API
  app/
    main.py        — app: mounts /api routers, migrations + ensure_settings on startup,
                     USDC wallet poll task, serves built SPA from static_spa/ if present
    config.py, db.py, util.py
    models/__init__.py — ALL SQLAlchemy models in one file
    migrations.py  — Alembic wrapper run on startup
    seed.py        — OPTIONAL demo data + default settings (nothing forced/undeletable)
    api/           — thin JSON endpoints, one file per feature (deps.py = shared helpers)
    serializers.py — explicit ORM→dict (domain dataclasses returned as-is via jsonable_encoder)
    services/      — business logic; no FastAPI imports
  alembic/, tests/, requirements.txt, .venv/ (uv)
frontend/         — Svelte 5 + Vite PWA
  src/
    main.ts, App.svelte (onboarding gate + router + add-operation sheet flow)
    app.css        — design tokens (dark, Inter + JetBrains Mono, semantic colors)
    lib/api.ts     — typed fetch client for /api
    lib/stores.ts  — period, hash route, toast, dataVersion(invalidate)
    lib/format.ts  — money / usdc / dates / month names
    lib/wallet.ts  — USDC wallet status store (drives the Dashboard balance flip)
    lib/components/ — BottomSheet, Toast, MoneyInput, ProgressBar, TxForm,
                      Chart, BottomNav, Onboarding, Login
    routes/        — Dashboard, Transactions (full history: multi-select/group filters,
                      period presets, day/month grouping with totals), Plan,
                      Deposit (standalone calculator, linked from More), Analytics, More, Faq
Dockerfile        — multi-stage: builds SPA → backend image serves API + static_spa/
Caddyfile         — TLS + reverse_proxy to budget-app:8000 (auth is app-level, not Caddy);
                    also proxies db.lunalis.tech → sqlite-web behind basic_auth (same creds)
```

**sqlite-web**: a lightweight SQLite admin UI, added as a `docker-compose.yml` service.
Locally on `127.0.0.1:8081` (`make db-ui`); in prod not exposed directly — only reachable
through Caddy at `db.lunalis.tech`, gated by the same `APP_USER`/`APP_PASSWORD_HASH`.

## Commands

```bash
make install     # backend venv (uv) + frontend npm install
make dev-api     # backend hot-reload → :8000
make dev-web     # Vite dev → :5173 (proxies /api to :8000)   [run in a 2nd terminal]
make test        # backend pytest
make db-ui       # sqlite-web (SQLite admin UI) → :8081, local Docker only

# Production (Docker, on VPS)
make hash-password p=secret   # bcrypt hash for the app login (.env APP_PASSWORD_HASH)
make prod-up                  # certs + Caddy + app
make prod-migrate
make deploy                   # git pull + rebuild (run on VPS)
```

`.env` (copy from `.env.example`): `APP_USER`, `APP_PASSWORD_HASH` (checked by `/api/auth/login`), `APP_SECRET` (signs the session cookie), `DATABASE_URL`.

## Key conventions

- **Frontend ↔ backend contract:** TS interfaces in `frontend/src/lib/api.ts` mirror `backend/app/serializers.py` and the domain dataclasses. Keep them in sync when changing either.
- **Routing is hash-based** (`#/plan`), so the server never needs an SPA fallback — `StaticFiles(html=True)` is enough.
- **Nothing is hardcoded/undeletable.** On first run the DB is empty; the onboarding screen offers demo data or a clean start. The 50/30/20 split works off `Category.group` / `Debt.type`, never off category names.
- **Optimistic-ish UI:** mutations call `invalidate()` (bumps `dataVersion`) so screens refetch; deletes show a Toast with undo.

## Data model highlights

- **Category.group**: `needs` / `wants` / `savings` / `income` — drives the 50/30/20 split. Income is recorded as a plain transaction and lands on the month balance as-is (the old income-allocation wizard was removed in July 2026).
- **SinkingFund** — envelope with optional `is_rolling` and `linked_category_id`.
- **MonthlyPlan** (CategoryLimit, PlannedExpense, PlannedDebtPayment) / Debt / Setting as before. **Deposit** is a standalone calculator (`app/services/deposit_calc.py` + `deposit` settings keys) — no ledger, no effect on the budget; the real вклад top-up is recorded as a normal expense in a `savings`-group category.

## Migrations

Alembic migrations in `backend/alembic/versions/`; `app/migrations.py` runs `upgrade head` on startup. To add one: `cd backend && .venv/bin/alembic revision --autogenerate -m "..."`.

## Telegram bot

Webhook-based bot (`app/api/telegram.py` → `POST /api/tg/webhook/{secret}`, public,
excluded from session auth). Free-form text is parsed by `services/ai/` (YandexGPT
→ GigaChat fallback via `router.py`) into `ParsedEntry`, resolved to categories/
people by `tx_resolver.py`, written immediately; the confirmation reply shows who
each operation was attributed to (`AppUser.name`, e.g. «· Общий»). `/stats` returns
an hour-cached digest (`services/daily_digest.py`) with a rotating AI/static tip —
the AI tip runs at a higher temperature (0.9, vs 0.3 for parsing) across several
modes/topics/styles for variety, and re-rolls every hour. Keys live in the
`Setting` table under `secret.*` (excluded from export, masked in GET), editable in
the app's «Интеграции» screen. People link to Telegram via `AppUser.telegram_id`
(also the access whitelist). Setup guide: `docs/telegram-bot-setup.md`.

## USDC wallet (Etherscan)

Personal read-only integration for a salary paid in USDC (`services/crypto_wallet.py` +
`api/wallet.py`, UI in the «Интеграции» screen + a flip on the Dashboard hero). An
asyncio task started in `main.py`'s lifespan polls Etherscan **V2**
(`api.etherscan.io/v2/api?chainid=1`, `action=tokenbalance`, USDC has 6 decimals)
every 5 minutes, caches the balance in `Setting` and sends **one Telegram message per
calendar month** once the balance crosses `wallet_threshold` (guard key
`wallet.alert_month`). Per-workspace keys: `wallet_address`, `wallet_threshold`,
`wallet_notify_user_id` + cache `wallet.{balance,checked_at,error,alert_month}`; the
Etherscan key is the install-wide secret `secret.etherscan_api_key`. The API never
returns the raw address — only a `0x5564…3148` mask. No ledger effect, no migrations.
Setup guide: `docs/usdc-wallet-setup.md`.

## Deployment

GitHub Actions → VPS on `git push origin main`; VPS runs `scripts/deploy.sh` (git pull + `make prod-rebuild` + `make prod-migrate`). Caddy serves HTTPS (self-signed cert via `scripts/gen-certs.sh`) and proxies to the app, which enforces its own login/session auth.
