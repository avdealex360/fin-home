# Telegram Bot with AI Expense Parsing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Telegram bot that parses free-form Russian expense/income text via YandexGPT/GigaChat (with fallback), writes transactions immediately to existing categories/people, serves a cached daily `/stats` digest with a rotating tip, exposes keys in an in-app "Integrations" screen, and moves the whole app onto `https://lunalis.tech` with Let's Encrypt.

**Architecture:** Webhook mode — the bot is a single public FastAPI route (no long-running process, no aiogram). AI providers sit behind one `complete()` interface with a fallback router. Secrets live in the existing key/value `Setting` table under a `secret.*` prefix, filtered out of exports and masked in GET. People are linked to Telegram accounts via `AppUser.telegram_id`, which doubles as the access whitelist.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, httpx (already a dependency), Svelte 5, Caddy (Let's Encrypt).

## Global Constraints

- **No new runtime dependencies** — use `httpx` (already in `backend/requirements.txt`); do NOT add aiogram/python-telegram-bot.
- **Secrets never leak** — any `Setting` key starting with `secret.` must be excluded from `GET /api/settings/export/json` and returned only masked from settings endpoints; write only on non-empty input.
- **All backend handlers are sync `def`** with `db: Session = Depends(get_db)` — match existing style (`backend/app/api/*.py`).
- **Webhook handler must never raise and must always return HTTP 200** — Telegram retries on non-2xx.
- **TS interfaces in `frontend/src/lib/api.ts` mirror backend serializers** — keep in sync.
- **Migration chain:** current head is `b2d3e4f5g6h7`; the new migration's `down_revision` is `b2d3e4f5g6h7`.
- **Alembic runs `upgrade head` on startup** (`app/migrations.py`) — no manual migrate step needed for the code to work in dev/prod.
- Commit messages: conventional commits, English.

## File Structure

**Backend — create:**
- `backend/alembic/versions/c3e4f5g6h7i8_add_telegram_id.py` — migration adding `app_users.telegram_id`.
- `backend/app/services/ai/__init__.py`
- `backend/app/services/ai/base.py` — `ParsedEntry`, `ParseContext`, `AiProvider`, `AiError`, prompt builders, JSON parser.
- `backend/app/services/ai/yandex.py` — YandexGPT provider.
- `backend/app/services/ai/gigachat.py` — GigaChat provider (OAuth token cache).
- `backend/app/services/ai/router.py` — provider factory + fallback (`parse_with_fallback`, `complete_with_fallback`).
- `backend/app/services/tg_client.py` — thin Telegram Bot API client.
- `backend/app/services/tx_resolver.py` — `ParsedEntry` → `Transaction`.
- `backend/app/services/telegram_bot.py` — update orchestration, commands, `_LAST_BATCH`.
- `backend/app/services/daily_digest.py` — `/stats` digest builder + daily cache.
- `backend/app/api/telegram.py` — `POST /api/tg/webhook/{secret}`.
- Tests: `backend/tests/test_ai_router.py`, `test_tx_resolver.py`, `test_telegram_bot.py`, `test_daily_digest.py`, `test_secret_settings.py`.

**Backend — modify:**
- `backend/app/models/__init__.py` — add `telegram_id` column to `AppUser`.
- `backend/app/serializers.py` — `user_dict` includes `telegram_id`.
- `backend/app/services/settings_store.py` — `get_secret`/`set_secret`/`secret_is_set`.
- `backend/app/api/settings.py` — filter `secret.*`; add integrations endpoints.
- `backend/app/api/meta.py` — accept `telegram_id` in user create/update.
- `backend/app/seed.py` — add non-secret defaults (`ai_primary_provider`, `tg_bot_enabled`).
- `backend/app/main.py` — register `telegram.router`; add `/api/tg/webhook` to `_PUBLIC_API_PREFIXES`.

**Frontend — modify:**
- `frontend/src/lib/api.ts` — `telegram_id` on `User`; integrations types + methods.
- `frontend/src/routes/More.svelte` — link to Integrations; `telegram_id` field on users.
- `frontend/src/routes/Integrations.svelte` — new screen (+ route wiring in `App.svelte`).

**Deploy/docs — modify/create:**
- `Caddyfile`, `docker-compose.prod.yml`, `.env.example`, `backend/app/config.py`.
- `docs/telegram-bot-setup.md` (create), `CLAUDE.md` (append section).

---

### Task 1: `AppUser.telegram_id` — model, migration, serializer

**Files:**
- Modify: `backend/app/models/__init__.py:14-17`
- Create: `backend/alembic/versions/c3e4f5g6h7i8_add_telegram_id.py`
- Modify: `backend/app/serializers.py:22-23`
- Test: `backend/tests/test_telegram_bot.py` (new file, first test)

**Interfaces:**
- Produces: `AppUser.telegram_id: str | None` (unique); `user_dict(u)` includes `"telegram_id"`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_telegram_bot.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app.db import Base
from app.models import AppUser
from app.serializers import user_dict


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_appuser_has_telegram_id_and_serializes(db):
    u = AppUser(name="Леша", telegram_id="12345")
    db.add(u)
    db.commit()
    d = user_dict(u)
    assert d["telegram_id"] == "12345"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_telegram_bot.py -v`
Expected: FAIL — `TypeError: 'telegram_id' is an invalid keyword argument` (or KeyError on the dict).

- [ ] **Step 3: Add the column to the model**

In `backend/app/models/__init__.py`, inside `class AppUser`, after the `is_active` line (currently line 15):

```python
    telegram_id: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
```

- [ ] **Step 4: Add it to the serializer**

In `backend/app/serializers.py`, change `user_dict`:

```python
def user_dict(u: AppUser) -> dict:
    return {"id": u.id, "name": u.name, "is_active": u.is_active, "telegram_id": u.telegram_id}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_telegram_bot.py -v`
Expected: PASS.

- [ ] **Step 6: Create the Alembic migration**

Create `backend/alembic/versions/c3e4f5g6h7i8_add_telegram_id.py`:

```python
"""add telegram_id to app_users

Revision ID: c3e4f5g6h7i8
Revises: b2d3e4f5g6h7
Create Date: 2026-07-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3e4f5g6h7i8"
down_revision: Union[str, None] = "b2d3e4f5g6h7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("app_users") as batch_op:
        batch_op.add_column(sa.Column("telegram_id", sa.String(length=32), nullable=True))
        batch_op.create_unique_constraint("uq_app_users_telegram_id", ["telegram_id"])


def downgrade() -> None:
    with op.batch_alter_table("app_users") as batch_op:
        batch_op.drop_constraint("uq_app_users_telegram_id", type_="unique")
        batch_op.drop_column("telegram_id")
```

- [ ] **Step 7: Verify migration applies on a fresh DB**

Run: `cd backend && .venv/bin/alembic upgrade head`
Expected: ends at `c3e4f5g6h7i8`, no error. (If `data/budget.db` already exists at head, this is a no-op — that's fine.)

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/__init__.py backend/app/serializers.py \
        backend/alembic/versions/c3e4f5g6h7i8_add_telegram_id.py \
        backend/tests/test_telegram_bot.py
git commit -m "feat: add telegram_id to AppUser (bot account link + whitelist)"
```

---

### Task 2: Secret helpers + export/GET filtering

**Files:**
- Modify: `backend/app/services/settings_store.py`
- Modify: `backend/app/api/settings.py:29-59`
- Modify: `backend/app/seed.py:46-56`
- Test: `backend/tests/test_secret_settings.py` (new)

**Interfaces:**
- Consumes: `get_setting`/`set_setting` from `settings_store`.
- Produces: `get_secret(db, key) -> str`, `set_secret(db, key, value) -> None` (writes only if `value` truthy), `secret_is_set(db, key) -> bool`, `mask_secret(value) -> str`. Constant `SECRET_PREFIX = "secret."`. `GET /api/settings` and `export_json` never include `secret.*` keys.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_secret_settings.py`:

```python
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app
from app.services.settings_store import get_secret, set_secret, secret_is_set, mask_secret


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_set_secret_skips_empty(db):
    set_secret(db, "secret.tg_bot_token", "abc123")
    assert get_secret(db, "secret.tg_bot_token") == "abc123"
    set_secret(db, "secret.tg_bot_token", "")  # empty = keep existing
    assert get_secret(db, "secret.tg_bot_token") == "abc123"
    assert secret_is_set(db, "secret.tg_bot_token") is True


def test_mask_secret():
    assert mask_secret("abcdef1234") == "••••1234"
    assert mask_secret("") == ""


def test_secret_excluded_from_export(db):
    set_secret(db, "secret.tg_bot_token", "supersecret")
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    resp = client.get("/api/settings/export/json")
    app.dependency_overrides.clear()
    payload = json.loads(resp.content)
    assert "secret.tg_bot_token" not in payload["settings"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_secret_settings.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_secret'`.

- [ ] **Step 3: Add secret helpers**

Append to `backend/app/services/settings_store.py`:

```python
SECRET_PREFIX = "secret."


def get_secret(db: Session, key: str, default: str = "") -> str:
    return get_setting(db, key, default)


def set_secret(db: Session, key: str, value: str) -> None:
    # Empty input means "leave the stored secret unchanged".
    if value:
        set_setting(db, key, value)


def secret_is_set(db: Session, key: str) -> bool:
    return bool(get_setting(db, key, ""))


def mask_secret(value: str) -> str:
    if not value:
        return ""
    return "••••" + value[-4:]
```

- [ ] **Step 4: Filter secrets from GET and export**

In `backend/app/api/settings.py`, update `get_settings` and `export_json`.

Replace the body of `get_settings` (currently lines 29-32) with:

```python
@router.get("")
def get_settings(db: Session = Depends(get_db)):
    keys = ["currency", "onboarded"]
    return {k: get_setting(db, k, "") for k in keys}
```

(unchanged, but confirm it lists explicit keys — it must never dump all rows).

In `export_json`, change the settings line (currently line 52) from:

```python
        "settings": {s.key: s.value for s in db.query(Setting).all()},
```

to:

```python
        "settings": {
            s.key: s.value
            for s in db.query(Setting).all()
            if not s.key.startswith("secret.")
        },
```

- [ ] **Step 5: Add non-secret defaults to seed**

In `backend/app/seed.py`, add to `DEFAULT_SETTINGS` (the dict at line 46), before `"onboarded"`:

```python
    "ai_primary_provider": "yandex",
    "tg_bot_enabled": "",
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_secret_settings.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/settings_store.py backend/app/api/settings.py \
        backend/app/seed.py backend/tests/test_secret_settings.py
git commit -m "feat: secret settings helpers + exclude secret.* from export"
```

---

### Task 3: AI base — types, prompts, JSON parser

**Files:**
- Create: `backend/app/services/ai/__init__.py` (empty)
- Create: `backend/app/services/ai/base.py`
- Test: `backend/tests/test_ai_router.py` (new file, first tests)

**Interfaces:**
- Produces:
  - `@dataclass ParsedEntry(amount: Decimal, type: str, category: str | None, person: str | None, date: date | None, comment: str | None, confidence: str)`
  - `@dataclass ParseContext(categories: list[dict], users: list[str], sender_name: str, today: date, currency: str)`
  - `class AiError(Exception)` — raised by providers on quota/transport/HTTP failure.
  - `class AiProvider(Protocol)` — attrs `name: str`; `complete(system: str, user: str) -> str`; `healthcheck() -> bool`.
  - `build_parse_messages(text: str, ctx: ParseContext) -> tuple[str, str]` → `(system, user)`.
  - `parse_entries(raw: str) -> list[ParsedEntry]` — parses model JSON output; raises `AiError` on unparseable/empty.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ai_router.py`:

```python
from datetime import date
from decimal import Decimal
import pytest

from app.services.ai.base import parse_entries, build_parse_messages, ParseContext, AiError


def test_parse_entries_valid_json():
    raw = '{"entries":[{"amount":1560,"type":"expense","category":"Продукты","person":null,"date":null,"comment":"магазин","confidence":"high"}]}'
    out = parse_entries(raw)
    assert len(out) == 1
    assert out[0].amount == Decimal("1560")
    assert out[0].type == "expense"
    assert out[0].category == "Продукты"
    assert out[0].date is None
    assert out[0].confidence == "high"


def test_parse_entries_with_iso_date():
    raw = '{"entries":[{"amount":360,"type":"expense","category":"Кофе","person":"Катя","date":"2026-07-01","comment":null,"confidence":"low"}]}'
    out = parse_entries(raw)
    assert out[0].date == date(2026, 7, 1)
    assert out[0].person == "Катя"


def test_parse_entries_strips_code_fence():
    raw = "```json\n{\"entries\":[{\"amount\":100,\"type\":\"expense\",\"category\":null,\"person\":null,\"date\":null,\"comment\":null,\"confidence\":\"high\"}]}\n```"
    out = parse_entries(raw)
    assert out[0].amount == Decimal("100")


def test_parse_entries_empty_raises():
    with pytest.raises(AiError):
        parse_entries("no json here")
    with pytest.raises(AiError):
        parse_entries('{"entries":[]}')


def test_build_parse_messages_includes_categories_and_today():
    ctx = ParseContext(
        categories=[{"id": 1, "name": "Продукты", "group": "needs"}],
        users=["Леша", "Катя", "Общий"],
        sender_name="Леша",
        today=date(2026, 7, 2),
        currency="RUB",
    )
    system, user = build_parse_messages("кофе 360", ctx)
    assert "Продукты" in system
    assert "2026-07-02" in system
    assert "кофе 360" in user
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_ai_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.ai'`.

- [ ] **Step 3: Create the package + base module**

Create empty `backend/app/services/ai/__init__.py`.

Create `backend/app/services/ai/base.py`:

```python
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol


class AiError(Exception):
    """Provider failed (quota, transport, HTTP, or unparseable output)."""


@dataclass
class ParsedEntry:
    amount: Decimal
    type: str  # "expense" | "income"
    category: str | None
    person: str | None
    date: date | None
    comment: str | None
    confidence: str  # "high" | "low"


@dataclass
class ParseContext:
    categories: list[dict]  # {"id", "name", "group"}
    users: list[str]
    sender_name: str
    today: date
    currency: str


class AiProvider(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str: ...

    def healthcheck(self) -> bool: ...


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def build_parse_messages(text: str, ctx: ParseContext) -> tuple[str, str]:
    cats = "\n".join(f'- {c["name"]} ({c["group"]})' for c in ctx.categories)
    people = ", ".join(ctx.users)
    system = (
        "Ты — парсер бытовых финансовых заметок семьи. Извлеки из текста список операций.\n"
        f"Сегодня: {ctx.today.isoformat()}. Валюта: {ctx.currency}.\n"
        f"Отправитель сообщения: {ctx.sender_name}.\n"
        f"Люди: {people}.\n"
        "Доступные категории (выбирай строго из этого списка, иначе null):\n"
        f"{cats}\n\n"
        "Верни СТРОГО JSON без пояснений в формате:\n"
        '{"entries":[{"amount":число,"type":"expense|income","category":"имя из списка или null",'
        '"person":"имя человека, или null","date":"YYYY-MM-DD или null","comment":"строка или null",'
        '"confidence":"high|low"}]}\n'
        "Правила: amount — число без пробелов и валюты. "
        "Относительные даты («вчера», «позавчера», «N дней назад», «в понедельник») "
        "вычисляй в YYYY-MM-DD от сегодняшней даты; если дата не упомянута — null. "
        "Зарплата/поступление → type=income, иначе expense. "
        "Если человек не назван — person=null. "
        "Если не уверен в категории или сумме — confidence=low."
    )
    return system, text


def _to_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _to_decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def parse_entries(raw: str) -> list[ParsedEntry]:
    match = _JSON_RE.search(raw or "")
    if not match:
        raise AiError("no JSON object in model output")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise AiError(f"invalid JSON: {e}") from e

    entries: list[ParsedEntry] = []
    for item in data.get("entries", []):
        amount = _to_decimal(item.get("amount"))
        if amount is None or amount <= 0:
            continue
        entries.append(
            ParsedEntry(
                amount=amount,
                type="income" if item.get("type") == "income" else "expense",
                category=item.get("category") or None,
                person=item.get("person") or None,
                date=_to_date(item.get("date")),
                comment=item.get("comment") or None,
                confidence="low" if item.get("confidence") == "low" else "high",
            )
        )
    if not entries:
        raise AiError("no usable entries")
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_ai_router.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/__init__.py backend/app/services/ai/base.py \
        backend/tests/test_ai_router.py
git commit -m "feat: AI base types, parse prompt builder, JSON entry parser"
```

---

### Task 4: YandexGPT provider

**Files:**
- Create: `backend/app/services/ai/yandex.py`
- Test: `backend/tests/test_ai_router.py` (append)

**Interfaces:**
- Consumes: `AiError` from `base`.
- Produces: `class YandexProvider(api_key: str, folder_id: str)` with `name = "yandex"`, `complete(system, user) -> str`, `healthcheck() -> bool`. Raises `AiError` on any HTTP/transport failure.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_ai_router.py`:

```python
import httpx
from app.services.ai.yandex import YandexProvider
from app.services.ai.base import AiError


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def test_yandex_complete_success(monkeypatch):
    def handler(request):
        assert "Api-Key testkey" == request.headers["Authorization"]
        body = {"result": {"alternatives": [{"message": {"text": "hello"}}]}}
        return httpx.Response(200, json=body)

    p = YandexProvider("testkey", "folder1")
    monkeypatch.setattr(p, "_client_factory", lambda: httpx.Client(transport=_mock_transport(handler)))
    assert p.complete("sys", "usr") == "hello"


def test_yandex_complete_quota_raises(monkeypatch):
    def handler(request):
        return httpx.Response(429, json={"error": "quota"})

    p = YandexProvider("testkey", "folder1")
    monkeypatch.setattr(p, "_client_factory", lambda: httpx.Client(transport=_mock_transport(handler)))
    with pytest.raises(AiError):
        p.complete("sys", "usr")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_ai_router.py -k yandex -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.ai.yandex'`.

- [ ] **Step 3: Implement the provider**

Create `backend/app/services/ai/yandex.py`:

```python
from __future__ import annotations

import httpx

from app.services.ai.base import AiError

_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
_TIMEOUT = 15.0


class YandexProvider:
    name = "yandex"

    def __init__(self, api_key: str, folder_id: str):
        self.api_key = api_key
        self.folder_id = folder_id

    def _client_factory(self) -> httpx.Client:
        return httpx.Client(timeout=_TIMEOUT)

    def complete(self, system: str, user: str) -> str:
        payload = {
            "modelUri": f"gpt://{self.folder_id}/yandexgpt-lite",
            "completionOptions": {"temperature": 0.3, "maxTokens": 2000},
            "messages": [
                {"role": "system", "text": system},
                {"role": "user", "text": user},
            ],
        }
        headers = {"Authorization": f"Api-Key {self.api_key}"}
        try:
            with self._client_factory() as client:
                resp = client.post(_URL, json=payload, headers=headers)
        except httpx.HTTPError as e:
            raise AiError(f"yandex transport: {e}") from e
        if resp.status_code != 200:
            raise AiError(f"yandex http {resp.status_code}: {resp.text[:200]}")
        try:
            return resp.json()["result"]["alternatives"][0]["message"]["text"]
        except (KeyError, IndexError, ValueError) as e:
            raise AiError(f"yandex bad response: {e}") from e

    def healthcheck(self) -> bool:
        try:
            self.complete("Ответь одним словом.", "ок")
            return True
        except AiError:
            return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_ai_router.py -k yandex -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/yandex.py backend/tests/test_ai_router.py
git commit -m "feat: YandexGPT AI provider with AiError on failure"
```

---

### Task 5: GigaChat provider (OAuth token cache)

**Files:**
- Create: `backend/app/services/ai/gigachat.py`
- Test: `backend/tests/test_ai_router.py` (append)

**Interfaces:**
- Consumes: `AiError` from `base`.
- Produces: `class GigaChatProvider(auth_key: str)` with `name = "gigachat"`, `complete(system, user) -> str`, `healthcheck() -> bool`. Caches the OAuth access token in-instance until ~30 min expiry.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_ai_router.py`:

```python
from app.services.ai.gigachat import GigaChatProvider


def test_gigachat_oauth_then_complete(monkeypatch):
    calls = {"oauth": 0}

    def handler(request):
        if request.url.path.endswith("/oauth"):
            calls["oauth"] += 1
            assert request.headers["Authorization"] == "Basic authkey"
            return httpx.Response(200, json={"access_token": "tok", "expires_at": 9999999999000})
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(200, json={"choices": [{"message": {"content": "answer"}}]})

    p = GigaChatProvider("authkey")
    monkeypatch.setattr(p, "_client_factory", lambda: httpx.Client(transport=_mock_transport(handler)))
    assert p.complete("sys", "usr") == "answer"
    p.complete("sys", "usr")  # token cached — no second oauth call
    assert calls["oauth"] == 1


def test_gigachat_quota_raises(monkeypatch):
    def handler(request):
        if request.url.path.endswith("/oauth"):
            return httpx.Response(200, json={"access_token": "tok", "expires_at": 9999999999000})
        return httpx.Response(429, json={})

    p = GigaChatProvider("authkey")
    monkeypatch.setattr(p, "_client_factory", lambda: httpx.Client(transport=_mock_transport(handler)))
    with pytest.raises(AiError):
        p.complete("sys", "usr")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_ai_router.py -k gigachat -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.ai.gigachat'`.

- [ ] **Step 3: Implement the provider**

Create `backend/app/services/ai/gigachat.py`:

```python
from __future__ import annotations

import time
import uuid

import httpx

from app.services.ai.base import AiError

_OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
_CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
_TIMEOUT = 15.0


class GigaChatProvider:
    name = "gigachat"

    def __init__(self, auth_key: str):
        self.auth_key = auth_key
        self._token: str | None = None
        self._token_exp: float = 0.0

    def _client_factory(self) -> httpx.Client:
        # GigaChat uses the Russian NUC CA; verify=False keeps setup simple for a
        # personal deployment (documented in the setup guide).
        return httpx.Client(timeout=_TIMEOUT, verify=False)

    def _ensure_token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        headers = {
            "Authorization": f"Basic {self.auth_key}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            with self._client_factory() as client:
                resp = client.post(_OAUTH_URL, headers=headers, data={"scope": "GIGACHAT_API_PERS"})
        except httpx.HTTPError as e:
            raise AiError(f"gigachat oauth transport: {e}") from e
        if resp.status_code != 200:
            raise AiError(f"gigachat oauth http {resp.status_code}")
        data = resp.json()
        self._token = data["access_token"]
        # expires_at is epoch millis; fall back to now+25min.
        self._token_exp = data.get("expires_at", 0) / 1000 or (time.time() + 1500)
        return self._token

    def complete(self, system: str, user: str) -> str:
        token = self._ensure_token()
        payload = {
            "model": "GigaChat",
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            with self._client_factory() as client:
                resp = client.post(_CHAT_URL, json=payload, headers=headers)
        except httpx.HTTPError as e:
            raise AiError(f"gigachat transport: {e}") from e
        if resp.status_code != 200:
            raise AiError(f"gigachat http {resp.status_code}: {resp.text[:200]}")
        try:
            return resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            raise AiError(f"gigachat bad response: {e}") from e

    def healthcheck(self) -> bool:
        try:
            self.complete("Ответь одним словом.", "ок")
            return True
        except AiError:
            return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_ai_router.py -k gigachat -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/gigachat.py backend/tests/test_ai_router.py
git commit -m "feat: GigaChat AI provider with cached OAuth token"
```

---

### Task 6: AI router — factory + fallback

**Files:**
- Create: `backend/app/services/ai/router.py`
- Test: `backend/tests/test_ai_router.py` (append)

**Interfaces:**
- Consumes: `YandexProvider`, `GigaChatProvider`, `AiError`, `ParsedEntry`, `ParseContext`, `build_parse_messages`, `parse_entries`; `get_secret`, `get_setting`.
- Produces:
  - `build_providers(db) -> list[AiProvider]` — ordered by `ai_primary_provider`, only those with credentials.
  - `complete_with_fallback(db, system, user) -> str | None` — first success, else `None`.
  - `parse_with_fallback(db, text, ctx) -> list[ParsedEntry]` — first provider whose output parses; `[]` if all fail.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_ai_router.py`:

```python
from app.services.ai import router as ai_router
from app.services.ai.base import ParseContext, ParsedEntry
from datetime import date as _date


class _FakeProvider:
    def __init__(self, name, output=None, fail=False):
        self.name = name
        self._output = output
        self._fail = fail

    def complete(self, system, user):
        if self._fail:
            raise AiError("boom")
        return self._output

    def healthcheck(self):
        return not self._fail


def _ctx():
    return ParseContext(categories=[{"id": 1, "name": "Кофе", "group": "wants"}],
                        users=["Леша"], sender_name="Леша", today=_date(2026, 7, 2), currency="RUB")


def test_parse_with_fallback_switches_on_failure(monkeypatch):
    good = '{"entries":[{"amount":360,"type":"expense","category":"Кофе","person":null,"date":null,"comment":null,"confidence":"high"}]}'
    providers = [_FakeProvider("yandex", fail=True), _FakeProvider("gigachat", output=good)]
    monkeypatch.setattr(ai_router, "build_providers", lambda db: providers)
    out = ai_router.parse_with_fallback(None, "кофе 360", _ctx())
    assert len(out) == 1 and out[0].amount == Decimal("360")


def test_parse_with_fallback_all_fail_returns_empty(monkeypatch):
    providers = [_FakeProvider("yandex", fail=True), _FakeProvider("gigachat", fail=True)]
    monkeypatch.setattr(ai_router, "build_providers", lambda db: providers)
    assert ai_router.parse_with_fallback(None, "кофе 360", _ctx()) == []


def test_complete_with_fallback(monkeypatch):
    providers = [_FakeProvider("yandex", fail=True), _FakeProvider("gigachat", output="tip")]
    monkeypatch.setattr(ai_router, "build_providers", lambda db: providers)
    assert ai_router.complete_with_fallback(None, "s", "u") == "tip"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_ai_router.py -k fallback -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.ai.router'`.

- [ ] **Step 3: Implement the router**

Create `backend/app/services/ai/router.py`:

```python
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.services.ai.base import (
    AiError,
    AiProvider,
    ParseContext,
    ParsedEntry,
    build_parse_messages,
    parse_entries,
)
from app.services.ai.gigachat import GigaChatProvider
from app.services.ai.yandex import YandexProvider
from app.services.settings_store import get_secret, get_setting

log = logging.getLogger("ai.router")


def build_providers(db: Session) -> list[AiProvider]:
    yandex_key = get_secret(db, "secret.yandex_api_key")
    yandex_folder = get_secret(db, "secret.yandex_folder_id")
    giga_key = get_secret(db, "secret.gigachat_auth_key")

    available: dict[str, AiProvider] = {}
    if yandex_key and yandex_folder:
        available["yandex"] = YandexProvider(yandex_key, yandex_folder)
    if giga_key:
        available["gigachat"] = GigaChatProvider(giga_key)

    primary = get_setting(db, "ai_primary_provider", "yandex")
    order = [primary] + [n for n in ("yandex", "gigachat") if n != primary]
    return [available[n] for n in order if n in available]


def complete_with_fallback(db: Session, system: str, user: str) -> str | None:
    for provider in build_providers(db):
        try:
            return provider.complete(system, user)
        except AiError as e:
            log.warning("provider %s failed: %s", provider.name, e)
    return None


def parse_with_fallback(db: Session, text: str, ctx: ParseContext) -> list[ParsedEntry]:
    system, user = build_parse_messages(text, ctx)
    for provider in build_providers(db):
        try:
            raw = provider.complete(system, user)
            return parse_entries(raw)
        except AiError as e:
            log.warning("provider %s parse failed: %s", provider.name, e)
    return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_ai_router.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/router.py backend/tests/test_ai_router.py
git commit -m "feat: AI router with provider factory and fallback chain"
```

---

### Task 7: Telegram Bot API client

**Files:**
- Create: `backend/app/services/tg_client.py`
- Test: `backend/tests/test_telegram_bot.py` (append)

**Interfaces:**
- Produces (all take an explicit bot `token`):
  - `send_message(token: str, chat_id: int | str, text: str) -> None`
  - `get_me(token: str) -> dict` — raises `TgError` on non-ok.
  - `set_webhook(token: str, url: str, secret_token: str) -> dict`
  - `class TgError(Exception)`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_telegram_bot.py`:

```python
import httpx
from app.services import tg_client
from app.services.tg_client import TgError


def test_get_me_ok(monkeypatch):
    def handler(request):
        assert "/bottok123/getMe" in request.url.path
        return httpx.Response(200, json={"ok": True, "result": {"username": "mybot"}})

    monkeypatch.setattr(tg_client, "_client_factory",
                        lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    assert tg_client.get_me("tok123")["username"] == "mybot"


def test_get_me_error_raises(monkeypatch):
    def handler(request):
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    monkeypatch.setattr(tg_client, "_client_factory",
                        lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(TgError):
        tg_client.get_me("bad")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_telegram_bot.py -k get_me -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.tg_client'`.

- [ ] **Step 3: Implement the client**

Create `backend/app/services/tg_client.py`:

```python
from __future__ import annotations

import logging

import httpx

_API = "https://api.telegram.org"
_TIMEOUT = 15.0
log = logging.getLogger("tg_client")


class TgError(Exception):
    pass


def _client_factory() -> httpx.Client:
    return httpx.Client(timeout=_TIMEOUT)


def _call(token: str, method: str, payload: dict) -> dict:
    url = f"{_API}/bot{token}/{method}"
    try:
        with _client_factory() as client:
            resp = client.post(url, json=payload)
    except httpx.HTTPError as e:
        raise TgError(f"transport: {e}") from e
    data = resp.json()
    if not data.get("ok"):
        raise TgError(f"{method} failed: {data.get('description')}")
    return data.get("result", {})


def send_message(token: str, chat_id: int | str, text: str) -> None:
    # Best-effort: log and swallow so a reply failure never breaks the webhook.
    try:
        _call(token, "sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
    except TgError as e:
        log.warning("sendMessage failed: %s", e)


def get_me(token: str) -> dict:
    return _call(token, "getMe", {})


def set_webhook(token: str, url: str, secret_token: str) -> dict:
    return _call(token, "setWebhook", {"url": url, "secret_token": secret_token})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_telegram_bot.py -k get_me -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tg_client.py backend/tests/test_telegram_bot.py
git commit -m "feat: thin Telegram Bot API client (httpx)"
```

---

### Task 8: Transaction resolver

**Files:**
- Create: `backend/app/services/tx_resolver.py`
- Test: `backend/tests/test_tx_resolver.py` (new)

**Interfaces:**
- Consumes: `ParsedEntry` from `ai.base`; models `Category`, `AppUser`, `Transaction`.
- Produces:
  - `resolve_category_id(db, name: str | None) -> int | None` — exact (case-insensitive) → substring → `None`.
  - `resolve_user_id(db, person: str | None, sender: AppUser | None) -> int | None` — matched person name, else sender's id.
  - `create_transactions(db, entries: list[ParsedEntry], sender: AppUser | None) -> list[Transaction]` — writes rows; when a category name was given but unresolved, appends `«{name}»?` marker to `comment`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_tx_resolver.py`:

```python
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AppUser, Category, Transaction
from app.services.ai.base import ParsedEntry
from app.services import tx_resolver


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add_all([
        Category(name="Продукты и быт", group="needs", sort_order=1),
        Category(name="Кофе", group="wants", sort_order=2),
        AppUser(name="Леша", telegram_id="111"),
        AppUser(name="Катя", telegram_id="222"),
        AppUser(name="Общий"),
    ])
    s.commit()
    yield s
    s.close()


def test_resolve_category_exact_and_substring(db):
    assert tx_resolver.resolve_category_id(db, "Кофе") is not None
    # substring / case-insensitive
    assert tx_resolver.resolve_category_id(db, "продукты") is not None
    assert tx_resolver.resolve_category_id(db, "Ракета") is None
    assert tx_resolver.resolve_category_id(db, None) is None


def test_resolve_user_defaults_to_sender(db):
    sender = db.query(AppUser).filter_by(name="Леша").first()
    assert tx_resolver.resolve_user_id(db, None, sender) == sender.id
    katya = db.query(AppUser).filter_by(name="Катя").first()
    assert tx_resolver.resolve_user_id(db, "Катя", sender) == katya.id


def test_create_transactions_writes_and_marks_unresolved(db):
    sender = db.query(AppUser).filter_by(name="Леша").first()
    entries = [
        ParsedEntry(Decimal("1560"), "expense", "Продукты и быт", None, None, "магазин", "high"),
        ParsedEntry(Decimal("999"), "expense", "Несуществующая", None, None, None, "low"),
    ]
    txs = tx_resolver.create_transactions(db, entries, sender)
    assert len(txs) == 2
    assert txs[0].category_id is not None and txs[0].user_id == sender.id
    assert txs[0].date == date.today()
    assert txs[1].category_id is None
    assert "Несуществующая" in (txs[1].comment or "")
    assert db.query(Transaction).count() == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_tx_resolver.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.tx_resolver'`.

- [ ] **Step 3: Implement the resolver**

Create `backend/app/services/tx_resolver.py`:

```python
from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AppUser, Category, Transaction
from app.services.ai.base import ParsedEntry


def resolve_category_id(db: Session, name: str | None) -> int | None:
    if not name:
        return None
    exact = (
        db.query(Category)
        .filter(func.lower(Category.name) == name.lower(), Category.is_hidden.is_(False))
        .first()
    )
    if exact:
        return exact.id
    like = (
        db.query(Category)
        .filter(Category.name.ilike(f"%{name}%"), Category.is_hidden.is_(False))
        .first()
    )
    return like.id if like else None


def resolve_user_id(db: Session, person: str | None, sender: AppUser | None) -> int | None:
    if person:
        match = db.query(AppUser).filter(func.lower(AppUser.name) == person.lower()).first()
        if match:
            return match.id
        if person.lower() in ("общее", "общий", "оба", "вместе"):
            common = db.query(AppUser).filter(AppUser.name.ilike("общ%")).first()
            if common:
                return common.id
    return sender.id if sender else None


def create_transactions(
    db: Session, entries: list[ParsedEntry], sender: AppUser | None
) -> list[Transaction]:
    created: list[Transaction] = []
    for e in entries:
        cat_id = resolve_category_id(db, e.category)
        comment = e.comment
        if e.category and cat_id is None:
            note = f"категория «{e.category}»?"
            comment = f"{comment} · {note}" if comment else note
        tx = Transaction(
            type=e.type,
            amount=e.amount,
            date=e.date or date.today(),
            category_id=cat_id,
            user_id=resolve_user_id(db, e.person, sender),
            comment=comment,
        )
        db.add(tx)
        created.append(tx)
    db.commit()
    for tx in created:
        db.refresh(tx)
    return created
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_tx_resolver.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tx_resolver.py backend/tests/test_tx_resolver.py
git commit -m "feat: resolve parsed entries to transactions (category/person)"
```

---

### Task 9: Daily digest (`/stats`)

**Files:**
- Create: `backend/app/services/daily_digest.py`
- Test: `backend/tests/test_daily_digest.py` (new)

**Interfaces:**
- Consumes: `complete_with_fallback` from `ai.router`; `get_setting`/`set_setting`; `Transaction`, `Category`, `AppUser`.
- Produces: `get_or_build(db, today: date | None = None) -> str`. Caches JSON under `Setting["digest.<iso>"]`. Constant `STATIC_TIPS: list[str]`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_daily_digest.py`:

```python
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AppUser, Category, Transaction, Setting
from app.services import daily_digest


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    cat = Category(name="Продукты", group="needs", sort_order=1)
    s.add(cat)
    s.commit()
    s.add(Transaction(type="expense", amount=Decimal("1560"), date=date.today(), category_id=cat.id))
    s.commit()
    yield s
    s.close()


def test_digest_caches_for_the_day(db, monkeypatch):
    calls = {"n": 0}

    def fake_complete(db_, system, user):
        calls["n"] += 1
        return "Совет: копи 10%."

    monkeypatch.setattr(daily_digest, "complete_with_fallback", fake_complete)
    first = daily_digest.get_or_build(db, today=date(2026, 7, 2))
    second = daily_digest.get_or_build(db, today=date(2026, 7, 2))
    assert first == second
    assert calls["n"] == 1  # AI called once, cached after
    assert db.query(Setting).filter(Setting.key == "digest.2026-07-02").first() is not None


def test_digest_falls_back_to_static_tip(db, monkeypatch):
    monkeypatch.setattr(daily_digest, "complete_with_fallback", lambda db_, s, u: None)
    text = daily_digest.get_or_build(db, today=date(2026, 7, 3))
    assert "1 560" in text or "1560" in text  # stats present
    assert len(text) > 0


def test_digest_rebuilds_on_new_day(db, monkeypatch):
    monkeypatch.setattr(daily_digest, "complete_with_fallback", lambda db_, s, u: "tip")
    a = daily_digest.get_or_build(db, today=date(2026, 7, 2))
    b = daily_digest.get_or_build(db, today=date(2026, 7, 4))
    assert db.query(Setting).filter(Setting.key == "digest.2026-07-04").first() is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_daily_digest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.daily_digest'`.

- [ ] **Step 3: Implement the digest**

Create `backend/app/services/daily_digest.py`:

```python
from __future__ import annotations

import json
import random
from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models import Category, Transaction
from app.services.ai.router import complete_with_fallback
from app.services.settings_store import get_setting, set_setting

STATIC_TIPS = [
    "Правило 50/30/20: 50% на нужды, 30% на желания, 20% в накопления.",
    "Собери подушку на 3–6 месяцев расходов — это защита от форс-мажоров.",
    "Перед крупной покупкой выжди сутки: импульс часто проходит.",
    "Автоматизируй откладывание в день зарплаты — платишь сначала себе.",
    "Веди учёт хотя бы неделю — увидишь, куда реально утекают деньги.",
]

_GROUP_LABELS = {"needs": "Нужды", "wants": "Желания", "savings": "Накопления"}


def _fmt(amount: Decimal | float) -> str:
    return f"{float(amount):,.0f}".replace(",", " ")


def _collect_stats(db: Session, today: date) -> dict:
    year, month = today.year, today.month
    q = db.query(Transaction).filter(
        Transaction.type == "expense",
        extract("year", Transaction.date) == year,
        extract("month", Transaction.date) == month,
    )
    total = sum((t.amount for t in q.all()), Decimal("0"))

    by_group: dict[str, Decimal] = {}
    top_cat = (
        db.query(Category.name, func.sum(Transaction.amount).label("s"))
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.type == "expense",
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) == month,
        )
        .group_by(Category.name)
        .order_by(func.sum(Transaction.amount).desc())
        .first()
    )
    for cat, amount in (
        db.query(Category.group, func.sum(Transaction.amount))
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.type == "expense",
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) == month,
        )
        .group_by(Category.group)
        .all()
    ):
        by_group[cat] = amount or Decimal("0")

    return {
        "total": total,
        "top_category": top_cat[0] if top_cat else None,
        "top_amount": top_cat[1] if top_cat else Decimal("0"),
        "by_group": by_group,
    }


def _stats_text(stats: dict) -> str:
    lines = [f"📊 Расходы за месяц: <b>{_fmt(stats['total'])} ₽</b>"]
    if stats["top_category"]:
        lines.append(f"Топ-категория: {stats['top_category']} ({_fmt(stats['top_amount'])} ₽)")
    for g, label in _GROUP_LABELS.items():
        if g in stats["by_group"]:
            lines.append(f"{label}: {_fmt(stats['by_group'][g])} ₽")
    return "\n".join(lines)


def _build_tip(db: Session, stats: dict) -> str:
    mode = random.choice(["stats", "literacy"])
    if mode == "stats":
        system = "Ты — дружелюбный финансовый помощник. Дай один короткий персональный совет (1–2 предложения) по цифрам семьи. Без вступлений."
        user = (
            f"Расходы за месяц: {_fmt(stats['total'])} ₽. "
            f"Топ-категория: {stats['top_category']} ({_fmt(stats['top_amount'])} ₽). "
            "Дай практичный совет."
        )
    else:
        system = "Ты — финансовый просветитель. Дай один короткий совет по финансовой грамотности (1–2 предложения) на случайную тему. Без вступлений."
        user = "Тема на твой выбор: подушка, проценты, импульсивные траты, правило 50/30/20, подписки."
    tip = complete_with_fallback(db, system, user)
    return tip.strip() if tip else random.choice(STATIC_TIPS)


def get_or_build(db: Session, today: date | None = None) -> str:
    today = today or date.today()
    key = f"digest.{today.isoformat()}"
    cached = get_setting(db, key, "")
    if cached:
        data = json.loads(cached)
        return f"{data['stats_text']}\n\n💡 {data['tip_text']}"

    stats = _collect_stats(db, today)
    stats_text = _stats_text(stats)
    tip_text = _build_tip(db, stats)
    set_setting(db, key, json.dumps({"stats_text": stats_text, "tip_text": tip_text}, ensure_ascii=False))
    return f"{stats_text}\n\n💡 {tip_text}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_daily_digest.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/daily_digest.py backend/tests/test_daily_digest.py
git commit -m "feat: /stats daily digest with cached rotating tip"
```

---

### Task 10: Bot orchestration + webhook route + main wiring

**Files:**
- Create: `backend/app/services/telegram_bot.py`
- Create: `backend/app/api/telegram.py`
- Modify: `backend/app/main.py:8-19` (import), `:60` (public prefix), `:87-99` (router include)
- Test: `backend/tests/test_telegram_bot.py` (append)

**Interfaces:**
- Consumes: `parse_with_fallback`, `ParseContext` (ai); `tx_resolver`; `daily_digest`; `tg_client`; `get_secret`; `Category`, `AppUser`.
- Produces:
  - `telegram_bot.handle_update(db, update: dict) -> None` — full pipeline; sends replies; never raises.
  - `telegram_bot._LAST_BATCH: dict[str, list[int]]` (module global, for `/undo`).
  - Route `POST /api/tg/webhook/{secret}` verifying secret path == `secret.tg_webhook_secret` and header `X-Telegram-Bot-Api-Secret-Token`; returns `{"ok": True}` always (403 only on secret mismatch).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_telegram_bot.py`:

```python
from decimal import Decimal
from datetime import date
from app.models import Category, Transaction
from app.services import telegram_bot
from app.services.ai.base import ParsedEntry


def _seed_people_and_cats(db):
    db.add_all([
        Category(name="Кофе", group="wants", sort_order=1),
        AppUser(name="Леша", telegram_id="111"),
    ])
    db.commit()


def test_handle_update_writes_transaction(db, monkeypatch):
    _seed_people_and_cats(db)
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "tok" if "token" in k else "wh")
    monkeypatch.setattr(
        telegram_bot, "parse_with_fallback",
        lambda d, text, ctx: [ParsedEntry(Decimal("360"), "expense", "Кофе", None, None, "кофе", "high")],
    )
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message", lambda token, chat_id, text: sent.append(text))

    update = {"message": {"text": "кофе 360", "chat": {"id": 111}, "from": {"id": 111}}}
    telegram_bot.handle_update(db, update)

    assert db.query(Transaction).count() == 1
    assert sent and "360" in sent[0]


def test_handle_update_rejects_unknown_sender(db, monkeypatch):
    _seed_people_and_cats(db)
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "tok")
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message", lambda token, chat_id, text: sent.append(text))
    update = {"message": {"text": "кофе 360", "chat": {"id": 999}, "from": {"id": 999}}}
    telegram_bot.handle_update(db, update)
    assert db.query(Transaction).count() == 0


def test_webhook_wrong_secret_returns_403(db, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import get_db
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "rightsecret")
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    r = client.post("/api/tg/webhook/wrongsecret", json={})
    app.dependency_overrides.clear()
    assert r.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_telegram_bot.py -k "handle_update or webhook" -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.telegram_bot'`.

- [ ] **Step 3: Implement the orchestrator**

Create `backend/app/services/telegram_bot.py`:

```python
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.models import AppUser, Category, Transaction
from app.services.ai.base import ParseContext
from app.services.ai.router import parse_with_fallback
from app.services.daily_digest import get_or_build as build_digest
from app.services.settings_store import get_secret, get_setting
from app.services.tg_client import send_message
from app.services.tx_resolver import create_transactions

log = logging.getLogger("telegram_bot")

# Per-sender id of the last written batch, for /undo. In-memory only.
_LAST_BATCH: dict[str, list[int]] = {}

_HELP = (
    "Пришли трату свободным текстом, например:\n"
    "<i>магазин 1560, кофе 360, интернет 1200</i>\n\n"
    "Команды:\n"
    "/stats — статистика и совет дня\n"
    "/undo — отменить последнюю запись\n"
    "/help — эта справка"
)


def _sender(db: Session, tg_id: str) -> AppUser | None:
    return db.query(AppUser).filter(AppUser.telegram_id == tg_id).first()


def handle_update(db: Session, update: dict) -> None:
    try:
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return
        text = (msg.get("text") or "").strip()
        chat_id = msg["chat"]["id"]
        tg_id = str(msg["from"]["id"])
        token = get_secret(db, "secret.tg_bot_token")
        if not token:
            log.warning("no bot token configured")
            return

        sender = _sender(db, tg_id)
        if sender is None:
            send_message(token, chat_id,
                         f"Аккаунт не привязан. Твой Telegram ID: <code>{tg_id}</code>. "
                         "Впиши его в приложении (More → Интеграции).")
            return

        if text in ("/start", "/help"):
            send_message(token, chat_id, _HELP)
            return
        if text == "/stats":
            send_message(token, chat_id, build_digest(db))
            return
        if text == "/undo":
            _handle_undo(db, token, chat_id, tg_id)
            return
        if not text:
            return

        _handle_text(db, token, chat_id, tg_id, sender, text)
    except Exception:  # webhook must never raise
        log.exception("handle_update failed")


def _handle_text(db, token, chat_id, tg_id, sender, text) -> None:
    ctx = ParseContext(
        categories=[
            {"id": c.id, "name": c.name, "group": c.group}
            for c in db.query(Category).filter(Category.is_hidden.is_(False)).all()
        ],
        users=[u.name for u in db.query(AppUser).filter(AppUser.is_active.is_(True)).all()],
        sender_name=sender.name,
        today=date.today(),
        currency=get_setting(db, "currency", "RUB"),
    )
    entries = parse_with_fallback(db, text, ctx)
    if not entries:
        send_message(token, chat_id, "Не смог разобрать 🤔 Попробуй иначе: «кофе 360, магазин 1560».")
        return

    txs = create_transactions(db, entries, sender)
    _LAST_BATCH[tg_id] = [t.id for t in txs]

    total = sum(t.amount for t in txs)
    lines = [f"✅ {len(txs)} операц. на <b>{float(total):,.0f}".replace(",", " ") + " ₽</b>"]
    for t, e in zip(txs, entries):
        cat = db.query(Category).get(t.category_id).name if t.category_id else "без категории"
        warn = " ⚠️ проверь" if (e.confidence != "high" or t.category_id is None) else ""
        lines.append(f"• {float(t.amount):,.0f}".replace(",", " ") + f" ₽ — {cat}{warn}")
    send_message(token, chat_id, "\n".join(lines))


def _handle_undo(db, token, chat_id, tg_id) -> None:
    ids = _LAST_BATCH.pop(tg_id, [])
    if not ids:
        send_message(token, chat_id, "Нечего отменять.")
        return
    db.query(Transaction).filter(Transaction.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    send_message(token, chat_id, f"↩️ Удалено операций: {len(ids)}.")
```

- [ ] **Step 4: Implement the webhook route**

Create `backend/app/api/telegram.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.settings_store import get_secret
from app.services.telegram_bot import handle_update

router = APIRouter(prefix="/api/tg", tags=["telegram"])


@router.post("/webhook/{secret}")
async def webhook(
    secret: str,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    expected = get_secret(db, "secret.tg_webhook_secret")
    if not expected or secret != expected or x_telegram_bot_api_secret_token != expected:
        return JSONResponse({"detail": "forbidden"}, status_code=403)
    update = await request.json()
    handle_update(db, update)
    return {"ok": True}
```

- [ ] **Step 5: Wire it into `main.py`**

In `backend/app/main.py`:

1. Add `telegram` to the imports (the `from app.api import (...)` block, lines 8-19):

```python
from app.api import (
    allocation,
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
```

2. Add the webhook prefix to `_PUBLIC_API_PREFIXES` (line 60):

```python
_PUBLIC_API_PREFIXES = ("/api/auth", "/api/health", "/api/docs", "/api/openapi.json", "/api/tg/webhook")
```

3. Add `telegram.router` to the router include tuple (lines 87-99), after `settings.router,`:

```python
    settings.router,
    telegram.router,
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_telegram_bot.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 7: Run the full backend suite**

Run: `cd backend && .venv/bin/pytest -v`
Expected: all pass (no regressions).

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/telegram_bot.py backend/app/api/telegram.py \
        backend/app/main.py backend/tests/test_telegram_bot.py
git commit -m "feat: telegram webhook route + bot orchestration (parse/write/stats/undo)"
```

---

### Task 11: Integrations settings API

**Files:**
- Modify: `backend/app/api/settings.py` (add integrations endpoints)
- Modify: `backend/app/api/meta.py:47-75` (accept `telegram_id` on users)
- Test: `backend/tests/test_secret_settings.py` (append)

**Interfaces:**
- Consumes: `get_secret`/`set_secret`/`secret_is_set`/`mask_secret`; `get_setting`/`set_setting`; `tg_client`; `ai.router.build_providers`; `get_settings()` (config, for `app_base_url`).
- Produces:
  - `GET /api/settings/integrations` → `{ "yandex_api_key": bool, "yandex_folder_id": bool, "gigachat_auth_key": bool, "tg_bot_token": bool, "tg_bot_token_mask": str, "ai_primary_provider": str, "tg_bot_enabled": bool, "webhook_set": bool }` (secrets as "is set" booleans + a mask, never raw).
  - `POST /api/settings/integrations` — body of optional secret fields + `ai_primary_provider` + `tg_bot_enabled`; writes non-empty.
  - `POST /api/settings/integrations/test` → `{ "telegram": bool, "yandex": bool, "gigachat": bool }`.
  - `POST /api/settings/integrations/set-webhook` → `{ "ok": bool, "url": str }`.
  - `meta` user create/update accept optional `telegram_id`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_secret_settings.py`:

```python
def test_integrations_get_reports_flags_not_raw(db):
    set_secret(db, "secret.yandex_api_key", "yakey")
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    r = client.get("/api/settings/integrations")
    app.dependency_overrides.clear()
    body = r.json()
    assert body["yandex_api_key"] is True
    assert body["gigachat_auth_key"] is False
    assert "yakey" not in json.dumps(body)


def test_integrations_post_saves_nonempty(db):
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    client.post("/api/settings/integrations", json={
        "yandex_api_key": "newkey", "yandex_folder_id": "", "ai_primary_provider": "gigachat",
    })
    app.dependency_overrides.clear()
    assert get_secret(db, "secret.yandex_api_key") == "newkey"
    from app.services.settings_store import get_setting
    assert get_setting(db, "ai_primary_provider") == "gigachat"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_secret_settings.py -k integrations -v`
Expected: FAIL — 404 on `/api/settings/integrations`.

- [ ] **Step 3: Add integrations endpoints**

In `backend/app/api/settings.py`, add imports at the top (after existing imports):

```python
import secrets as secrets_mod

from app.config import get_settings as get_app_settings
from app.services.ai.router import build_providers
from app.services.settings_store import (
    get_secret,
    mask_secret,
    secret_is_set,
    set_secret,
)
from app.services.tg_client import TgError, get_me, set_webhook
```

Then append these endpoints to the router:

```python
_SECRET_FIELDS = ["tg_bot_token", "yandex_api_key", "yandex_folder_id", "gigachat_auth_key"]


class IntegrationsBody(BaseModel):
    tg_bot_token: str | None = None
    yandex_api_key: str | None = None
    yandex_folder_id: str | None = None
    gigachat_auth_key: str | None = None
    ai_primary_provider: str | None = None
    tg_bot_enabled: bool | None = None


@router.get("/integrations")
def get_integrations(db: Session = Depends(get_db)):
    out = {f: secret_is_set(db, f"secret.{f}") for f in _SECRET_FIELDS}
    out["tg_bot_token_mask"] = mask_secret(get_secret(db, "secret.tg_bot_token"))
    out["ai_primary_provider"] = get_setting(db, "ai_primary_provider", "yandex")
    out["tg_bot_enabled"] = get_setting(db, "tg_bot_enabled", "") == "1"
    out["webhook_set"] = secret_is_set(db, "secret.tg_webhook_secret")
    return out


@router.post("/integrations")
def save_integrations(body: IntegrationsBody, db: Session = Depends(get_db)):
    for f in _SECRET_FIELDS:
        val = getattr(body, f)
        if val is not None:
            set_secret(db, f"secret.{f}", val)
    if body.ai_primary_provider in ("yandex", "gigachat"):
        set_setting(db, "ai_primary_provider", body.ai_primary_provider)
    if body.tg_bot_enabled is not None:
        set_setting(db, "tg_bot_enabled", "1" if body.tg_bot_enabled else "")
    return {"ok": True}


@router.post("/integrations/test")
def test_integrations(db: Session = Depends(get_db)):
    result = {"telegram": False, "yandex": False, "gigachat": False}
    token = get_secret(db, "secret.tg_bot_token")
    if token:
        try:
            get_me(token)
            result["telegram"] = True
        except TgError:
            result["telegram"] = False
    for provider in build_providers(db):
        result[provider.name] = provider.healthcheck()
    return result


@router.post("/integrations/set-webhook")
def set_bot_webhook(db: Session = Depends(get_db)):
    token = get_secret(db, "secret.tg_bot_token")
    if not token:
        return {"ok": False, "url": "", "error": "no bot token"}
    base = get_app_settings().app_base_url.rstrip("/")
    if not base:
        return {"ok": False, "url": "", "error": "APP_BASE_URL not set"}
    webhook_secret = get_secret(db, "secret.tg_webhook_secret")
    if not webhook_secret:
        webhook_secret = secrets_mod.token_urlsafe(24)
        set_secret(db, "secret.tg_webhook_secret", webhook_secret)
    url = f"{base}/api/tg/webhook/{webhook_secret}"
    try:
        set_webhook(token, url, webhook_secret)
        return {"ok": True, "url": url}
    except TgError as e:
        return {"ok": False, "url": url, "error": str(e)}
```

- [ ] **Step 4: Accept `telegram_id` on users**

In `backend/app/api/meta.py`, update `UserBody` and the create/update handlers (lines 48-75):

```python
class UserBody(BaseModel):
    name: str
    telegram_id: str | None = None


@router.post("/users")
def create_user(body: UserBody, db: Session = Depends(get_db)):
    u = AppUser(name=body.name, telegram_id=body.telegram_id or None)
    db.add(u)
    db.commit()
    db.refresh(u)
    return user_dict(u)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserBody, db: Session = Depends(get_db)):
    u = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not u:
        raise HTTPException(404, "user not found")
    u.name = body.name
    u.telegram_id = body.telegram_id or None
    db.commit()
    db.refresh(u)
    return user_dict(u)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_secret_settings.py -v`
Expected: PASS.

- [ ] **Step 6: Full suite**

Run: `cd backend && .venv/bin/pytest -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/settings.py backend/app/api/meta.py backend/tests/test_secret_settings.py
git commit -m "feat: integrations settings API (keys, test, set-webhook) + user telegram_id"
```

---

### Task 12: Frontend API client

**Files:**
- Modify: `frontend/src/lib/api.ts` (User interface + integrations types/methods)

**Interfaces:**
- Consumes: `req<T>` helper (line 148), `api` object (line 185).
- Produces: `User.telegram_id: string | null`; `Integrations` interface; `api.integrations()`, `api.saveIntegrations()`, `api.testIntegrations()`, `api.setWebhook()`; `createUser`/`updateUser` accept `telegram_id`.

- [ ] **Step 1: Add `telegram_id` to the `User` interface**

In `frontend/src/lib/api.ts`, update the `User` interface (currently ends with `is_active: boolean`):

```typescript
export interface User {
  id: number
  name: string
  is_active: boolean
  telegram_id: string | null
}
```

- [ ] **Step 2: Add the Integrations interface**

Add near the other interfaces:

```typescript
export interface Integrations {
  tg_bot_token: boolean
  yandex_api_key: boolean
  yandex_folder_id: boolean
  gigachat_auth_key: boolean
  tg_bot_token_mask: string
  ai_primary_provider: 'yandex' | 'gigachat'
  tg_bot_enabled: boolean
  webhook_set: boolean
}
```

- [ ] **Step 3: Add methods to the `api` object**

Inside the `export const api = { ... }` object (after `saveSettings`, line ~277), add:

```typescript
  integrations: () => req<Integrations>('GET', '/settings/integrations'),
  saveIntegrations: (b: Partial<{
    tg_bot_token: string; yandex_api_key: string; yandex_folder_id: string;
    gigachat_auth_key: string; ai_primary_provider: string; tg_bot_enabled: boolean
  }>) => req('POST', '/settings/integrations', b),
  testIntegrations: () => req<{ telegram: boolean; yandex: boolean; gigachat: boolean }>('POST', '/settings/integrations/test'),
  setWebhook: () => req<{ ok: boolean; url: string; error?: string }>('POST', '/settings/integrations/set-webhook'),
```

- [ ] **Step 4: Ensure user create/update send telegram_id**

Find the existing `createUser`/`updateUser` methods in the `api` object and confirm they pass the whole body. If they are typed to `{ name: string }`, widen to include `telegram_id`:

```typescript
  createUser: (b: { name: string; telegram_id?: string | null }) => req<User>('POST', '/users', b),
  updateUser: (id: number, b: { name: string; telegram_id?: string | null }) => req<User>('PATCH', `/users/${id}`, b),
```

- [ ] **Step 5: Typecheck**

Run: `cd frontend && npm run build`
Expected: build succeeds (no TS errors).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(web): api client for integrations + user telegram_id"
```

---

### Task 13: Integrations screen + More link + user binding

**Files:**
- Create: `frontend/src/routes/Integrations.svelte`
- Modify: `frontend/src/App.svelte` (route wiring for `#/integrations`)
- Modify: `frontend/src/routes/More.svelte` (link + telegram_id field on users)

**Interfaces:**
- Consumes: `api.integrations`, `api.saveIntegrations`, `api.testIntegrations`, `api.setWebhook`, `api.updateUser`; `showToast`.

Routing note: `App.svelte` uses a `$route` store where hash `#/deposit` maps to
`$route === 'deposit'` (no leading slash). The new screen is `#/integrations` →
`$route === 'integrations'`.

- [ ] **Step 1: Create the Integrations screen**

Create `frontend/src/routes/Integrations.svelte`:

```svelte
<script lang="ts">
  import { api, type Integrations } from '../lib/api'
  import { showToast } from '../lib/stores'

  let s = $state<Integrations | null>(null)
  let form = $state({
    tg_bot_token: '', yandex_api_key: '', yandex_folder_id: '', gigachat_auth_key: '',
    ai_primary_provider: 'yandex' as 'yandex' | 'gigachat', tg_bot_enabled: false,
  })
  let testing = $state(false)
  let testResult = $state<{ telegram: boolean; yandex: boolean; gigachat: boolean } | null>(null)

  async function load() {
    s = await api.integrations()
    form.ai_primary_provider = s.ai_primary_provider
    form.tg_bot_enabled = s.tg_bot_enabled
  }
  load()

  async function save() {
    const body: any = { ai_primary_provider: form.ai_primary_provider, tg_bot_enabled: form.tg_bot_enabled }
    for (const k of ['tg_bot_token', 'yandex_api_key', 'yandex_folder_id', 'gigachat_auth_key'] as const) {
      if (form[k]) body[k] = form[k]
    }
    await api.saveIntegrations(body)
    form.tg_bot_token = form.yandex_api_key = form.yandex_folder_id = form.gigachat_auth_key = ''
    await load()
    showToast('Сохранено')
  }
  async function test() {
    testing = true
    try { testResult = await api.testIntegrations() } finally { testing = false }
  }
  async function webhook() {
    const r = await api.setWebhook()
    showToast(r.ok ? 'Webhook установлен' : `Ошибка: ${r.error ?? 'не удалось'}`)
    await load()
  }

  function ph(isSet: boolean, mask = '') {
    return isSet ? (mask || 'задан ••••') : 'не задан'
  }
</script>

<div class="wrap">
  <a class="btn btn-ghost" href="#/more"><i class="ti ti-arrow-left"></i> Назад</a>
  <h2>Интеграции</h2>

  {#if s}
  <section class="card">
    <h3>Telegram-бот</h3>
    <label>Токен бота
      <input type="password" bind:value={form.tg_bot_token} placeholder={ph(s.tg_bot_token, s.tg_bot_token_mask)} />
    </label>
    <label class="row">
      <input type="checkbox" bind:checked={form.tg_bot_enabled} /> Бот включён
    </label>
    <button class="btn btn-ghost" onclick={webhook}>
      {s.webhook_set ? 'Переустановить webhook' : 'Установить webhook'}
    </button>
  </section>

  <section class="card">
    <h3>AI-провайдеры</h3>
    <label>YandexGPT — API-ключ
      <input type="password" bind:value={form.yandex_api_key} placeholder={ph(s.yandex_api_key)} />
    </label>
    <label>Yandex folder id
      <input type="password" bind:value={form.yandex_folder_id} placeholder={ph(s.yandex_folder_id)} />
    </label>
    <label>GigaChat — Authorization key
      <input type="password" bind:value={form.gigachat_auth_key} placeholder={ph(s.gigachat_auth_key)} />
    </label>
    <label>Основной провайдер
      <select bind:value={form.ai_primary_provider}>
        <option value="yandex">YandexGPT</option>
        <option value="gigachat">GigaChat</option>
      </select>
    </label>
  </section>

  <div class="row">
    <button class="btn btn-primary" onclick={save}>Сохранить</button>
    <button class="btn btn-ghost" onclick={test} disabled={testing}>
      {testing ? 'Проверяю…' : 'Проверить'}
    </button>
  </div>

  {#if testResult}
    <div class="card">
      <div>Telegram: {testResult.telegram ? '✅' : '❌'}</div>
      <div>YandexGPT: {testResult.yandex ? '✅' : '❌'}</div>
      <div>GigaChat: {testResult.gigachat ? '✅' : '❌'}</div>
    </div>
  {/if}
  {/if}
</div>

<style>
  .wrap { display: flex; flex-direction: column; gap: 12px; padding-bottom: 40px; }
  .card { display: flex; flex-direction: column; gap: 10px; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 14px; }
  label.row { flex-direction: row; align-items: center; gap: 8px; }
  .row { display: flex; gap: 8px; align-items: center; }
</style>
```

- [ ] **Step 2: Wire the route in `App.svelte`**

Add the import next to the other route imports (near line 15-20):

```typescript
  import Integrations from './routes/Integrations.svelte'
```

and add the branch in the `{#if $route === ...}` chain, after the `transactions` branch:

```svelte
    {:else if $route === 'integrations'}
      <Integrations />
```

- [ ] **Step 3: Add the More link**

In `frontend/src/routes/More.svelte`, add a link next to the existing ones (after the "Калькулятор вклада" link, line 116):

```svelte
  <a class="btn btn-ghost faq-btn" href="#/integrations"><i class="ti ti-robot"></i> Телеграм-бот и AI</a>
```

- [ ] **Step 4: Add telegram_id field to the user rows in More.svelte**

Find the user list rendering and edit form. Add a `telegram_id` input to the user edit UI, and include it when saving. Locate `saveUserEdit` (line 43) and the editing state; extend the edit state with a telegram id and pass it:

In the `<script>`, add:
```typescript
  let editingUserTgId = $state<string>('')
```
Update `startEditUser`:
```typescript
  function startEditUser(u: User) {
    editingUserId = u.id
    editingUserName = u.name
    editingUserTgId = u.telegram_id ?? ''
  }
```
Update `saveUserEdit`:
```typescript
  async function saveUserEdit() {
    if (editingUserId == null) return
    await api.updateUser(editingUserId, { name: editingUserName, telegram_id: editingUserTgId || null })
    editingUserId = null
    invalidate()
  }
```
In the user edit markup (where `editingUserName` is bound), add below the name input:
```svelte
    <input bind:value={editingUserTgId} placeholder="Telegram ID (для бота)" />
```

- [ ] **Step 5: Build to typecheck**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 6: Manual smoke via preview**

Start the app (backend + frontend), open `#/integrations`, confirm the screen renders and "Сохранить"/"Проверить" call the API without console errors. (Use the preview tools; no keys needed to verify rendering.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/routes/Integrations.svelte frontend/src/App.svelte frontend/src/routes/More.svelte
git commit -m "feat(web): integrations screen + bot link + user telegram_id field"
```

---

### Task 14: Deploy — domain, Let's Encrypt, config

**Files:**
- Modify: `Caddyfile`
- Modify: `docker-compose.prod.yml`
- Modify: `.env.example`
- Modify: `backend/app/config.py` (already has `app_base_url`; confirm)

**Interfaces:**
- Produces: Caddy serves `https://lunalis.tech` with auto Let's Encrypt; `APP_BASE_URL` available to the app.

- [ ] **Step 1: Update the Caddyfile**

Replace the whole `backend`-facing config in `Caddyfile` with a domain block:

```
{
	servers {
		protocols h1 h2
	}
}

lunalis.tech {
	reverse_proxy budget-app:8000
}

:80 {
	redir https://lunalis.tech{uri} permanent
}
```

(Caddy issues and renews the Let's Encrypt cert automatically. The old `:443 { tls /certs/... }` self-signed block is removed.)

- [ ] **Step 2: Point compose env at the domain**

In `docker-compose.prod.yml`, ensure the app has `APP_BASE_URL`. The app already uses `env_file: .env`, so no compose change is strictly required if `.env` holds it. If the caddy service still mounts `./certs`, that mount is now unused but harmless — leave it or remove the `- ./certs:/certs:ro` line. Confirm caddy keeps `caddy_data`/`caddy_config` volumes (needed to persist ACME certs).

- [ ] **Step 3: Add APP_BASE_URL to .env.example**

Append to `.env.example`:

```
# --- Telegram bot / AI ---
# Публичный HTTPS-адрес приложения (для setWebhook). После перехода на домен:
APP_BASE_URL=https://lunalis.tech
```

- [ ] **Step 4: Confirm config field**

Verify `backend/app/config.py` has `app_base_url: str = ""` (it does). No change needed.

- [ ] **Step 5: Commit**

```bash
git add Caddyfile docker-compose.prod.yml .env.example
git commit -m "feat(deploy): serve app on lunalis.tech with Let's Encrypt"
```

---

### Task 15: Documentation

**Files:**
- Create: `docs/telegram-bot-setup.md`
- Modify: `CLAUDE.md` (append a short bot section)

- [ ] **Step 1: Write the setup guide**

Create `docs/telegram-bot-setup.md` with these sections (full prose, not placeholders):

```markdown
# Телеграм-бот: настройка и подключение

Бот принимает свободный текст («магазин 1560, кофе 360, интернет 1200»),
разбирает его через YandexGPT/GigaChat и сразу записывает операции в бюджет.
Команды: свободный текст (запись), `/stats` (статистика + совет дня), `/undo`, `/help`.

## 1. Домен и сертификат
1. В DNS домена `lunalis.tech` добавь A-запись: `lunalis.tech → 194.154.29.93`.
   Дождись распространения (`dig lunalis.tech +short` должен вернуть IP).
2. Задеплой с новым `Caddyfile` (домен + Let's Encrypt). Caddy сам выпустит
   сертификат при первом обращении по HTTPS. Проверь: `https://lunalis.tech`
   открывается без предупреждения о сертификате.
3. В `.env` на сервере укажи `APP_BASE_URL=https://lunalis.tech`, перезапусти app.

## 2. Создание бота
1. В Telegram напиши @BotFather → `/newbot`, задай имя и username.
2. Скопируй токен вида `123456:ABC-...`.

## 3. Ключи YandexGPT (Yandex Cloud)
1. Создай каталог (folder) в Yandex Cloud, запомни его **folder id**.
2. Создай сервисный аккаунт, дай роль `ai.languageModels.user`.
3. Создай для него **API-ключ**, скопируй значение.

## 4. Ключ GigaChat (Сбер)
1. На developers.sber.ru получи доступ к GigaChat API (тариф для физлиц).
2. Возьми **Authorization key** (base64 от `client_id:client_secret`).

## 5. Ввод ключей в приложении
1. Открой приложение → More → «Телеграм-бот и AI».
2. Вставь токен бота, ключи Yandex (API-ключ + folder id) и/или GigaChat.
3. Выбери основного провайдера, включи «Бот включён», нажми «Сохранить».
4. Нажми «Проверить» — все настроенные пункты должны быть ✅.
5. Нажми «Установить webhook».

## 6. Привязка людей
1. Каждый член семьи пишет боту `/start` — бот вернёт его Telegram ID.
2. В More открой правку человека, впиши его Telegram ID, сохрани.
3. Только привязанные аккаунты могут писать боту.

## 7. Отладка
- **403 на webhook** — не совпал секрет; переустанови webhook в «Интеграции».
- **AI 401/ошибка** — проверь ключи кнопкой «Проверить».
- **Кончилась квота одного провайдера** — бот сам переключится на второго.
- **⚠️ проверь у операции** — AI не уверен или не распознал категорию;
  поправь операцию вручную в приложении.
- Логи webhook: `make prod-logs` (ищи `telegram_bot` / `ai.router`).
```

- [ ] **Step 2: Append a section to CLAUDE.md**

Add to `CLAUDE.md` (after the "Data model highlights" section):

```markdown
## Telegram bot

Webhook-based bot (`app/api/telegram.py` → `POST /api/tg/webhook/{secret}`, public,
excluded from session auth). Free-form text is parsed by `services/ai/` (YandexGPT
→ GigaChat fallback via `router.py`) into `ParsedEntry`, resolved to categories/
people by `tx_resolver.py`, written immediately. `/stats` returns a day-cached
digest (`services/daily_digest.py`) with a rotating AI/static tip. Keys live in the
`Setting` table under `secret.*` (excluded from export, masked in GET), editable in
the app's «Интеграции» screen. People link to Telegram via `AppUser.telegram_id`
(also the access whitelist). Setup guide: `docs/telegram-bot-setup.md`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/telegram-bot-setup.md CLAUDE.md
git commit -m "docs: Telegram bot setup guide + CLAUDE.md section"
```

---

## Final verification

- [ ] **Backend suite green**

Run: `cd backend && .venv/bin/pytest -v`
Expected: all tests pass.

- [ ] **Frontend builds**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Migration applies cleanly on a throwaway DB**

Run: `cd backend && rm -f /tmp/t.db && DATABASE_URL=sqlite:////tmp/t.db .venv/bin/alembic upgrade head`
Expected: ends at `c3e4f5g6h7i8`, no error.

- [ ] **Push the branch for autodeploy**

```bash
git push -u origin feat/telegram-bot-ai
```

(Merge to `main` triggers the GitHub Actions → VPS deploy. Do the DNS A-record and `.env` `APP_BASE_URL` before/with the deploy per `docs/telegram-bot-setup.md`.)
