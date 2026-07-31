from types import SimpleNamespace

import bcrypt

from app.services import auth as auth_module


def _fake_settings(app_secret="test-secret"):
    return SimpleNamespace(app_secret=app_secret)


def test_session_token_roundtrip(monkeypatch):
    monkeypatch.setattr(auth_module, "get_settings", lambda: _fake_settings())
    token = auth_module.create_session_token(42)
    assert auth_module.session_account_id(token) == 42


def test_session_token_rejects_tampering(monkeypatch):
    monkeypatch.setattr(auth_module, "get_settings", lambda: _fake_settings())
    token = auth_module.create_session_token(42)
    account, ts, sig = token.split(".")
    # Forged account id with the original signature must fail.
    assert auth_module.session_account_id(f"43.{ts}.{sig}") is None
    assert auth_module.session_account_id(f"{account}.{ts}9.{sig}") is None


def test_session_token_rejects_wrong_secret(monkeypatch):
    monkeypatch.setattr(auth_module, "get_settings", lambda: _fake_settings(app_secret="a"))
    token = auth_module.create_session_token(1)
    monkeypatch.setattr(auth_module, "get_settings", lambda: _fake_settings(app_secret="b"))
    assert auth_module.session_account_id(token) is None


def test_session_token_expires(monkeypatch):
    monkeypatch.setattr(auth_module, "get_settings", lambda: _fake_settings())
    token = auth_module.create_session_token(1)
    monkeypatch.setattr(auth_module.time, "time", lambda: 10**12)
    assert auth_module.session_account_id(token) is None


def test_session_account_id_rejects_garbage():
    assert auth_module.session_account_id(None) is None
    assert auth_module.session_account_id("") is None
    assert auth_module.session_account_id("no-dot-here") is None
    assert auth_module.session_account_id("one.dot") is None
    assert auth_module.session_account_id("a.b.c") is None


def test_verify_password():
    hashed = bcrypt.hashpw(b"secret123", bcrypt.gensalt()).decode()
    assert auth_module.verify_password("secret123", hashed)
    assert not auth_module.verify_password("wrong", hashed)
    assert not auth_module.verify_password("anything", "")
    assert not auth_module.verify_password("anything", None)


def test_hash_password_roundtrip():
    hashed = auth_module.hash_password("pass-1234")
    assert auth_module.verify_password("pass-1234", hashed)


def test_login_flow_and_middleware(api):
    client = api.client
    # Real bcrypt hash for the seeded account.
    from app.models import Account

    s = api.Session()
    acc = s.get(Account, api.account_id)
    acc.password_hash = auth_module.hash_password("secret123")
    s.commit()
    s.close()

    # Fresh client without the fixture's cookie.
    client.cookies.clear()
    assert client.get("/api/funds").status_code == 401
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is False

    resp = client.post("/api/auth/login", json={"username": "budget", "password": "nope"})
    assert resp.status_code == 401

    resp = client.post("/api/auth/login", json={"username": "budget", "password": "secret123"})
    assert resp.status_code == 200
    assert auth_module.SESSION_COOKIE in resp.cookies
    assert client.get("/api/funds").status_code == 200
    me = client.get("/api/auth/me").json()
    assert me["authenticated"] is True
    assert me["username"] == "budget"
    assert me["is_admin"] is True
    assert me["workspace"]["id"] == api.ws_id

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").json()["authenticated"] is False
    assert client.get("/api/funds").status_code == 401


def test_deactivated_account_is_rejected(api):
    from app.models import Account

    s = api.Session()
    s.query(Account).filter(Account.id == api.account_id).update({"is_active": False})
    s.commit()
    s.close()
    assert api.client.get("/api/funds").status_code == 401


def test_invite_registration_creates_workspace(api):
    client = api.client
    invite = client.post("/api/admin/invites", json={"label": "для друга"}).json()
    assert invite["token"]

    info = client.get(f"/api/auth/invite/{invite['token']}").json()
    assert info["valid"] is True and info["mode"] == "create"

    # Register from a clean client (no session).
    client.cookies.clear()
    resp = client.post("/api/auth/register", json={
        "token": invite["token"], "username": "friend", "password": "friendpass",
        "workspace_name": "Бюджет друга",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["workspace"]["name"] == "Бюджет друга"
    me = client.get("/api/auth/me").json()
    assert me["authenticated"] is True and me["username"] == "friend"
    assert me["is_admin"] is False
    assert me["workspace"]["id"] != api.ws_id

    # Single-use: the same token can't register twice.
    client.cookies.clear()
    resp = client.post("/api/auth/register", json={
        "token": invite["token"], "username": "friend2", "password": "friendpass2",
    })
    assert resp.status_code == 400


def test_invite_join_existing_workspace(api):
    client = api.client
    invite = client.post(
        "/api/admin/invites", json={"label": "жена", "workspace_id": api.ws_id}
    ).json()
    info = client.get(f"/api/auth/invite/{invite['token']}").json()
    assert info["mode"] == "join"

    client.cookies.clear()
    resp = client.post("/api/auth/register", json={
        "token": invite["token"], "username": "partner", "password": "partnerpass",
    })
    assert resp.status_code == 200
    assert resp.json()["workspace"]["id"] == api.ws_id


def test_workspace_isolation(api):
    client = api.client
    # Workspace A creates a category and a transaction.
    client.post("/api/onboarding", json={"mode": "clean"})
    cat = client.post("/api/categories", json={"name": "Продукты", "group": "needs"}).json()
    tx = client.post("/api/transactions", json={
        "type": "expense", "amount": 500, "category_id": cat["id"],
    }).json()

    # A friend registers into their own workspace.
    invite = client.post("/api/admin/invites", json={}).json()
    client.cookies.clear()
    resp = client.post("/api/auth/register", json={
        "token": invite["token"], "username": "friend", "password": "friendpass",
    })
    assert resp.status_code == 200

    # The friend sees an empty, un-onboarded workspace.
    assert client.get("/api/onboarding").json()["onboarded"] is False
    assert client.get("/api/categories").json() == []
    assert client.get("/api/transactions").json()["total"] == 0

    # Cross-workspace access by id is a 404 (or a no-op delete).
    assert client.patch(f"/api/transactions/{tx['id']}", json={
        "type": "expense", "amount": 1,
    }).status_code == 404
    assert client.patch(f"/api/categories/{cat['id']}", json={
        "name": "x", "group": "needs",
    }).status_code == 404
    client.delete(f"/api/transactions/{tx['id']}")

    # Friend is not an admin.
    assert client.get("/api/admin/overview").status_code == 403
    assert client.get("/api/settings/integrations").status_code == 403

    # Original data is intact for workspace A.
    from app.services.auth import SESSION_COOKIE, create_session_token

    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, create_session_token(api.account_id))
    assert client.get("/api/transactions").json()["total"] == 1


def test_admin_overview_and_account_management(api):
    client = api.client
    from app.services.auth import SESSION_COOKIE, create_session_token

    overview = client.get("/api/admin/overview").json()
    assert len(overview["workspaces"]) == 1
    assert overview["workspaces"][0]["accounts"][0]["username"] == "budget"

    invite = client.post("/api/admin/invites", json={}).json()
    client.cookies.clear()
    client.post("/api/auth/register", json={
        "token": invite["token"], "username": "friend", "password": "friendpass",
    })
    # Back to the admin session.
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, create_session_token(api.account_id))

    overview = client.get("/api/admin/overview").json()
    assert len(overview["workspaces"]) == 2

    friend_id = next(
        a["id"]
        for w in overview["workspaces"]
        for a in w["accounts"]
        if a["username"] == "friend"
    )
    assert client.patch(f"/api/admin/accounts/{friend_id}", json={"is_active": False}).status_code == 200
    # Deactivating your own admin account is blocked.
    assert client.patch(f"/api/admin/accounts/{api.account_id}", json={"is_active": False}).status_code == 400
