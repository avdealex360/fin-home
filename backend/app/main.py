from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    analytics,
    auth,
    debts,
    deposit,
    funds,
    meta,
    plan,
    settings,
    telegram,
    transactions,
)
from app.db import SessionLocal
from app.migrations import run_migrations
from app.seed import ensure_common_user, ensure_savings_category, ensure_settings
from app.services.ai_trace import LOG_FILE, trace_block
from app.services.auth import SESSION_COOKIE, is_valid_session

DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "backups").mkdir(exist_ok=True)

_BUILD_ID = Path("/app/BUILD_ID")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    db = SessionLocal()
    try:
        ensure_settings(db)
        ensure_savings_category(db)
        ensure_common_user(db)
    finally:
        db.close()
    build_id = _BUILD_ID.read_text(encoding="utf-8").strip() if _BUILD_ID.is_file() else "local"
    trace_block("app.started", build_id=build_id, log_file=str(LOG_FILE.resolve()))
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

_PUBLIC_API_PREFIXES = ("/api/auth", "/api/health", "/api/docs", "/api/openapi.json", "/api/tg/webhook")


@app.middleware("http")
async def require_session(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api") and not path.startswith(_PUBLIC_API_PREFIXES):
        if not is_valid_session(request.cookies.get(SESSION_COOKIE)):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


# The SPA shell (index.html) and service worker must never be served stale —
# iOS Safari's disk cache for installed PWAs is notoriously sticky, and a stale
# shell after a deploy is a prime cause of a white screen / stuck spinner on
# reopen. Hashed files under /assets/* are immutable and unaffected.
_NO_CACHE_PATHS = {"/", "/index.html", "/sw.js", "/registerSW.js", "/manifest.webmanifest"}


@app.middleware("http")
async def no_cache_shell(request: Request, call_next):
    response = await call_next(request)
    if request.url.path in _NO_CACHE_PATHS:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


for router in (
    auth.router,
    meta.router,
    transactions.router,
    funds.router,
    debts.router,
    plan.router,
    deposit.router,
    analytics.router,
    settings.router,
    telegram.router,
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
