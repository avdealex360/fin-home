from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    allocation,
    analytics,
    debts,
    deposit,
    funds,
    meta,
    plan,
    settings,
    transactions,
)
from app.db import SessionLocal
from app.migrations import run_migrations
from app.seed import ensure_settings

DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "backups").mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    db = SessionLocal()
    try:
        ensure_settings(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="fin-home API",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# In production Caddy serves the SPA from the same origin and proxies /api, so
# CORS is a no-op there. For local `vite dev` (port 5173) we allow the dev origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    meta.router,
    transactions.router,
    allocation.router,
    funds.router,
    debts.router,
    plan.router,
    deposit.router,
    analytics.router,
    settings.router,
):
    app.include_router(router)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}


# Serve the built SPA if present (production image). The frontend uses hash-based
# routing, so every browser navigation requests "/" — no SPA fallback needed and
# StaticFiles(html=True) is enough. In dev the dist dir is absent and Vite serves it.
_SPA_DIR = Path("static_spa")
if _SPA_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_SPA_DIR), html=True), name="spa")
