from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import SessionLocal
from app.middleware.auth import BasicAuthMiddleware
from app.migrations import run_migrations
from app.routers import (
    allocation,
    analytics,
    checkup,
    dashboard,
    deposit,
    goals,
    plan,
    settings,
    sinking_funds,
    telegram,
    transactions,
)
from app.seed import seed_database

DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "backups").mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Семейный бюджет", lifespan=lifespan)
app.add_middleware(BasicAuthMiddleware)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse("app/static/favicon.svg", media_type="image/svg+xml")


app.include_router(dashboard.router)
app.include_router(transactions.router)
app.include_router(allocation.router)
app.include_router(sinking_funds.router)
app.include_router(plan.router)
app.include_router(analytics.router)
app.include_router(deposit.router)
app.include_router(goals.router)
app.include_router(checkup.router)
app.include_router(settings.router)
app.include_router(telegram.router)
