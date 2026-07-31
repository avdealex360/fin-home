"""Shared fixtures for the multi-tenant test suite."""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers models with Base.metadata
from app.db import Base
from app.models import Account, Workspace

WS = 1  # default workspace id used by unit-test fixtures


def create_workspace(session, name="Тест", onboarded="") -> Workspace:
    ws = Workspace(name=name, onboarded=onboarded)
    session.add(ws)
    session.commit()
    session.refresh(ws)
    return ws


def create_account(session, ws_id: int, username="budget", is_admin=True) -> Account:
    acc = Account(
        username=username,
        password_hash="not-a-real-hash",
        workspace_id=ws_id,
        is_admin=is_admin,
    )
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc


@pytest.fixture
def api(tmp_path, monkeypatch):
    """A TestClient logged in as an admin account in its own workspace.

    File-based SQLite so TestClient worker threads share the DB, and
    main.SessionLocal is patched so the auth middleware resolves accounts
    from the same test database.
    """
    from fastapi.testclient import TestClient

    import app.main as main
    from app.db import get_db
    from app.services.auth import SESSION_COOKIE, create_session_token

    engine = create_engine(
        f"sqlite:///{tmp_path / 'test_api.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    s = TestSession()
    ws = create_workspace(s)
    acc = create_account(s, ws.id)
    ws_id, account_id = ws.id, acc.id
    s.close()

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides = {get_db: override_get_db}
    monkeypatch.setattr(main, "SessionLocal", TestSession)

    client = TestClient(main.app)
    client.cookies.set(SESSION_COOKIE, create_session_token(account_id))

    yield SimpleNamespace(
        client=client,
        Session=TestSession,
        ws_id=ws_id,
        account_id=account_id,
        engine=engine,
    )

    main.app.dependency_overrides = {}
    engine.dispose()
