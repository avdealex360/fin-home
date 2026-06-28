from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import Base, SessionLocal, engine
from app.middleware.auth import BasicAuthMiddleware
from app.routers import analytics, dashboard, deposit, goals, plan, settings, telegram, transactions
from app.seed import seed_database

DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "backups").mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Семейный бюджет", lifespan=lifespan)
app.add_middleware(BasicAuthMiddleware)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(dashboard.router)
app.include_router(transactions.router)
app.include_router(plan.router)
app.include_router(analytics.router)
app.include_router(deposit.router)
app.include_router(goals.router)
app.include_router(settings.router)
app.include_router(telegram.router)
