from types import SimpleNamespace

import bcrypt

from app.services import auth as auth_module


def _fake_settings(app_secret="test-secret", app_password_hash=None, app_user="budget"):
    return SimpleNamespace(app_secret=app_secret, app_password_hash=app_password_hash, app_user=app_user)


def test_session_token_roundtrip(monkeypatch):
    monkeypatch.setattr(auth_module, "get_settings", lambda: _fake_settings())
    token = auth_module.create_session_token()
    assert auth_module.is_valid_session(token)


def test_session_token_rejects_tampering(monkeypatch):
    monkeypatch.setattr(auth_module, "get_settings", lambda: _fake_settings())
    token = auth_module.create_session_token()
    payload, sig = token.split(".", 1)
    assert not auth_module.is_valid_session(f"{payload}9.{sig}")


def test_session_token_rejects_wrong_secret(monkeypatch):
    monkeypatch.setattr(auth_module, "get_settings", lambda: _fake_settings(app_secret="a"))
    token = auth_module.create_session_token()
    monkeypatch.setattr(auth_module, "get_settings", lambda: _fake_settings(app_secret="b"))
    assert not auth_module.is_valid_session(token)


def test_session_token_expires(monkeypatch):
    monkeypatch.setattr(auth_module, "get_settings", lambda: _fake_settings())
    token = auth_module.create_session_token()
    monkeypatch.setattr(auth_module.time, "time", lambda: 10**12)
    assert not auth_module.is_valid_session(token)


def test_is_valid_session_rejects_garbage():
    assert not auth_module.is_valid_session(None)
    assert not auth_module.is_valid_session("")
    assert not auth_module.is_valid_session("no-dot-here")


def test_verify_password_correct(monkeypatch):
    hashed = bcrypt.hashpw(b"secret123", bcrypt.gensalt()).decode()
    monkeypatch.setattr(auth_module, "get_settings", lambda: _fake_settings(app_password_hash=hashed))
    assert auth_module.verify_password("secret123")
    assert not auth_module.verify_password("wrong")


def test_verify_password_no_hash_configured(monkeypatch):
    monkeypatch.setattr(auth_module, "get_settings", lambda: _fake_settings(app_password_hash=""))
    assert not auth_module.verify_password("anything")


def test_login_flow_and_middleware(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.main as main
    import app.models  # noqa: F401
    from app.db import Base, get_db

    hashed = bcrypt.hashpw(b"secret123", bcrypt.gensalt()).decode()
    fake = _fake_settings(app_secret="test-secret", app_password_hash=hashed, app_user="budget")
    monkeypatch.setattr(auth_module, "get_settings", lambda: fake)
    monkeypatch.setattr("app.api.auth.get_settings", lambda: fake)

    db_path = tmp_path / "test_auth.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides = {}
    main.app.dependency_overrides[get_db] = override_get_db
    client = TestClient(main.app)

    # No session yet — protected endpoints are blocked.
    assert client.get("/api/funds").status_code == 401
    # But auth/health/docs stay public.
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is False

    # Wrong password is rejected.
    resp = client.post("/api/auth/login", json={"username": "budget", "password": "nope"})
    assert resp.status_code == 401

    # Correct login sets a session cookie and unlocks the API.
    resp = client.post("/api/auth/login", json={"username": "budget", "password": "secret123"})
    assert resp.status_code == 200
    assert auth_module.SESSION_COOKIE in resp.cookies
    assert client.get("/api/funds").status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is True

    # Logout clears the session.
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").json()["authenticated"] is False
    assert client.get("/api/funds").status_code == 401

    main.app.dependency_overrides = {}
    engine.dispose()
