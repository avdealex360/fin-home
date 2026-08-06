import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    admin,
    analytics,
    auth,
    debts,
    deposit,
    funds,
    invest,
    meta,
    plan,
    settings,
    telegram,
    transactions,
    wallet,
)
from app.db import SessionLocal
from app.migrations import run_migrations
from app.seed import ensure_admin_account, ensure_startup_data
from app.services.ai_trace import LOG_FILE, trace_block
from app.services.auth import SESSION_COOKIE, session_account_id
from app.services.crypto_wallet import poll_loop as wallet_poll_loop

DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "backups").mkdir(exist_ok=True)

_BUILD_ID = Path("/app/BUILD_ID")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    db = SessionLocal()
    try:
        ensure_admin_account(db)
        ensure_startup_data(db)
    finally:
        db.close()
    build_id = _BUILD_ID.read_text(encoding="utf-8").strip() if _BUILD_ID.is_file() else "local"
    trace_block("app.started", build_id=build_id, log_file=str(LOG_FILE.resolve()))
    # Опрос USDC-кошельков: одна задача на процесс (uvicorn поднимается одним воркером).
    wallet_task = asyncio.create_task(wallet_poll_loop(SessionLocal))
    try:
        yield
    finally:
        wallet_task.cancel()
        try:
            await wallet_task
        except asyncio.CancelledError:
            pass


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
    """Validate the session cookie and resolve the account once per request.

    request.state gets account_id / workspace_id / is_admin for downstream
    dependencies (deps.ws_id, deps.require_admin). Public prefixes skip the
    gate but still get the identity resolved when a cookie is present
    (e.g. /api/auth/me)."""
    path = request.url.path
    account_id = session_account_id(request.cookies.get(SESSION_COOKIE))
    if account_id is not None:
        from app.models import Account

        db = SessionLocal()
        try:
            account = (
                db.query(Account)
                .filter(Account.id == account_id, Account.is_active.is_(True))
                .first()
            )
        finally:
            db.close()
        if account:
            request.state.account_id = account.id
            request.state.workspace_id = account.workspace_id
            request.state.is_admin = account.is_admin
        else:
            account_id = None
    if path.startswith("/api") and not path.startswith(_PUBLIC_API_PREFIXES):
        if account_id is None:
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
    admin.router,
    meta.router,
    transactions.router,
    funds.router,
    debts.router,
    plan.router,
    deposit.router,
    analytics.router,
    settings.router,
    telegram.router,
    wallet.router,
    invest.router,
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
