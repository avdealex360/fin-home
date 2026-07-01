# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A personal family budget web app (Russian UI) implementing the **50/30/20 rule**. Runs on a VPS behind Caddy. Mobile-first, self-hosted, installable as a PWA.

**Stack:** Svelte 5 + Vite (PWA SPA) · Python 3.12 · FastAPI (JSON API) · SQLite · SQLAlchemy 2.x · Alembic · Chart.js · Docker · Caddy

> **v3 (June 2026):** rewritten from the original HTMX/Jinja2 app into a Svelte SPA + JSON API split. The frontend is a single-page app served as static files; the backend speaks JSON only. Auth is app-level: a login screen posts to `/api/auth/login`, which sets a signed httponly session cookie (`app/services/auth.py`); a middleware in `main.py` gates all `/api/*` except `/api/auth/*`, `/api/health`, and docs.

## Repo layout

```
backend/          — FastAPI JSON API
  app/
    main.py        — app: mounts /api routers, migrations + ensure_settings on startup,
                     serves built SPA from static_spa/ if present
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
    lib/format.ts  — money / dates / month names
    lib/components/ — BottomSheet, Toast, MoneyInput, ProgressBar, TxForm,
                      AllocationSheet, Chart, BottomNav, Onboarding, Login
    routes/        — Dashboard, Plan, Deposit (standalone calculator, linked from More),
                      Analytics, More
Dockerfile        — multi-stage: builds SPA → backend image serves API + static_spa/
Caddyfile         — TLS + reverse_proxy to budget-app:8000 (auth is app-level, not Caddy)
```

## Commands

```bash
make install     # backend venv (uv) + frontend npm install
make dev-api     # backend hot-reload → :8000
make dev-web     # Vite dev → :5173 (proxies /api to :8000)   [run in a 2nd terminal]
make test        # backend pytest

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
- **Nothing is hardcoded/undeletable.** On first run the DB is empty; the onboarding screen offers demo data or a clean start. Allocation and the 50/30/20 split work off `Category.group` / `Debt.type`, never off category names.
- **Optimistic-ish UI:** mutations call `invalidate()` (bumps `dataVersion`) so screens refetch; deletes show a Toast with undo.

## Data model highlights

- **Category.group**: `needs` / `wants` / `savings` / `income` — drives the 50/30/20 split. `allocation_level` (1=obligations, 2=variable, 4=wants+savings; 3=funds) drives the income allocation wizard.
- **IncomeAllocation** — links an income `Transaction` to categories/funds at a level; `Transaction.is_fully_allocated` flips when fully distributed.
- **SinkingFund** — envelope with optional `is_rolling` and `linked_category_id`.
- **MonthlyPlan** (CategoryLimit, PlannedExpense, PlannedDebtPayment) / Debt / Setting as before. **Deposit** is a standalone calculator (`app/services/deposit_calc.py` + `deposit` settings keys) — no ledger, no effect on the budget; the real вклад top-up is recorded as a normal expense in a `savings`-group category.

## Migrations

Alembic migrations in `backend/alembic/versions/`; `app/migrations.py` runs `upgrade head` on startup. To add one: `cd backend && .venv/bin/alembic revision --autogenerate -m "..."`.

## Deployment

GitHub Actions → VPS on `git push origin main`; VPS runs `scripts/deploy.sh` (git pull + `make prod-rebuild` + `make prod-migrate`). Caddy serves HTTPS (self-signed cert via `scripts/gen-certs.sh`) and proxies to the app, which enforces its own login/session auth.
