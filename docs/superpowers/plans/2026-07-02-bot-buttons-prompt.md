# Bot v2: prompt tuning, provider label, keyboards, ask-category-on-null

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Improve the Telegram bot: (1) sharper AI prompt so a category is almost always chosen and the person (Я/Катя/Общее) is inferred better; (2) show which AI provider answered (YandexGPT/GigaChat) in both expense replies and `/stats`; (3) reply-keyboard buttons for commands; (4) when the AI leaves a category empty, ask the user to pick one via inline buttons (handle `callback_query`).

**Architecture:** All changes in the existing backend bot modules — no new services, no schema change. `parse_with_fallback`/`complete_with_fallback` start returning the winning provider name alongside their result. The webhook already receives `callback_query` updates (Telegram's default `allowed_updates` includes them), so no `setWebhook` change is needed.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, httpx. No new dependencies.

## Global Constraints

- **No new runtime dependencies.**
- **`handle_update` must never raise** and the webhook must keep returning 200 (except the existing 403 on secret mismatch). Any new branch (callback handling) lives inside the existing `try/except`.
- **Backend test runner:** `.venv/bin/python -m pytest` from `backend/` (bare `.venv/bin/pytest` → `ModuleNotFoundError: app`).
- **Whitelist still applies to callbacks:** a `callback_query` from a Telegram id not linked to an `AppUser` must not mutate data.
- **Keep the full suite green after every task** — a signature change and all its callers/tests must land in the same task.
- **`send_message` stays best-effort** (swallows send errors).
- Conventional commits, English.
- Provider display names: `yandex` → `YandexGPT`, `gigachat` → `GigaChat`.

## File structure

- `backend/app/services/ai/base.py` — `build_parse_messages` prompt rewrite (Task 1).
- `backend/app/services/ai/router.py` — return provider name; `provider_label()` helper (Task 2).
- `backend/app/services/daily_digest.py` — thread tip provider into cache + digest footer (Task 2).
- `backend/app/services/telegram_bot.py` — provider footer (Task 2); reply keyboard + button→command (Task 4); ask-category-on-null + `callback_query` handling (Task 5).
- `backend/app/services/tg_client.py` — `reply_markup` on `send_message`; `answer_callback_query` (Task 3).
- Tests: `backend/tests/test_ai_router.py`, `test_daily_digest.py`, `test_telegram_bot.py`.

---

### Task 1: Prompt tuning (always pick a category; better person)

**Files:**
- Modify: `backend/app/services/ai/base.py:46-67` (`build_parse_messages`)
- Test: `backend/tests/test_ai_router.py` (append one test)

**Interfaces:**
- `build_parse_messages(text, ctx) -> (system, user)` signature unchanged; only the `system` string content changes.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_ai_router.py`:

```python
def test_prompt_has_category_and_person_rules():
    from datetime import date as _d
    ctx = ParseContext(
        categories=[{"id": 1, "name": "Продукты", "group": "needs"}],
        users=["Леша", "Катя", "Общий"],
        sender_name="Леша",
        today=_d(2026, 7, 2),
        currency="RUB",
    )
    system, _ = build_parse_messages("корм коту 500", ctx)
    # category is always chosen unless truly nothing fits
    assert "ВСЕГДА" in system
    # shared/household expenses go to «Общее»
    assert "Общее" in system
    # still lists categories and today's date
    assert "Продукты" in system and "2026-07-02" in system
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_ai_router.py::test_prompt_has_category_and_person_rules -v`
Expected: FAIL (`assert "ВСЕГДА" in system`).

- [ ] **Step 3: Rewrite the prompt**

In `backend/app/services/ai/base.py`, replace the `system = (...)` assignment inside `build_parse_messages` (lines 49-66) with:

```python
    system = (
        "Ты — парсер бытовых финансовых заметок семьи. Извлеки из текста список операций.\n"
        f"Сегодня: {ctx.today.isoformat()}. Валюта: {ctx.currency}.\n"
        f"Отправитель сообщения: {ctx.sender_name}.\n"
        f"Люди: {people}.\n"
        "Доступные категории (выбирай ТОЛЬКО из этого списка):\n"
        f"{cats}\n\n"
        "Верни СТРОГО JSON без пояснений в формате:\n"
        '{"entries":[{"amount":число,"type":"expense|income","category":"имя из списка или null",'
        '"person":"имя человека, или null","date":"YYYY-MM-DD или null","comment":"строка или null",'
        '"confidence":"high|low"}]}\n'
        "Правила:\n"
        "- amount — число без пробелов и валюты.\n"
        "- category: ВСЕГДА выбирай одну наиболее близкую по смыслу категорию из списка "
        "(ремонт / газ / коммуналка / быт → бытовая нужда; еда вне дома / доставка → рестораны; "
        "сигареты / алкоголь / развлечения → развлечения; корм / ветеринар / питомец → категория питомца). "
        "Ставь category=null ТОЛЬКО если ни одна категория даже отдалённо не подходит; "
        "не сваливай всё в «Прочее» / «Буфер».\n"
        "- person: если в тексте назван человек — этот человек; "
        "если трата общая или бытовая (аренда, ремонт, коммуналка, интернет, продукты, питомец, уборка) — «Общее»; "
        "если это личное потребление (кофе, сигареты, личная одежда) — отправитель; иначе — отправитель.\n"
        "- Относительные даты («вчера», «позавчера», «N дней назад», «в понедельник») "
        "вычисляй в YYYY-MM-DD от сегодняшней даты; если дата не упомянута — null.\n"
        "- Зарплата / поступление → type=income, иначе expense.\n"
        "- confidence=low, если категория или человек выбраны по догадке.\n"
        "Примеры:\n"
        "«ремонт газа в квартире 1840» → category = ближайшая бытовая категория, person=«Общее».\n"
        "«корм коту 500» → category = категория питомца, person=«Общее».\n"
        "«сигареты 3500» → category = развлечения / личное, person=отправитель, confidence=low."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_ai_router.py -v`
Expected: PASS (new test + existing `test_build_parse_messages_includes_categories_and_today` still green).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/base.py backend/tests/test_ai_router.py
git commit -m "feat(bot): sharper parse prompt — always pick category, infer shared/personal payer"
```

---

### Task 2: Provider label end-to-end (router + digest + reply)

**Files:**
- Modify: `backend/app/services/ai/router.py:38-55`
- Modify: `backend/app/services/telegram_bot.py:83-97`
- Modify: `backend/app/services/daily_digest.py:83-111`
- Test: `backend/tests/test_ai_router.py`, `test_daily_digest.py`, `test_telegram_bot.py`

**Interfaces:**
- Produces:
  - `parse_with_fallback(db, text, ctx) -> tuple[list[ParsedEntry], str | None]`
  - `complete_with_fallback(db, system, user) -> tuple[str | None, str | None]`
  - `provider_label(name: str | None) -> str` (in `router.py`)
- The second tuple element is the winning provider's `name` (`"yandex"`/`"gigachat"`), or `None` if all failed.

- [ ] **Step 1: Update router tests (RED)**

In `backend/tests/test_ai_router.py`, replace the three fallback tests bodies:

```python
def test_parse_with_fallback_switches_on_failure(monkeypatch):
    good = '{"entries":[{"amount":360,"type":"expense","category":"Кофе","person":null,"date":null,"comment":null,"confidence":"high"}]}'
    providers = [_FakeProvider("yandex", fail=True), _FakeProvider("gigachat", output=good)]
    monkeypatch.setattr(ai_router, "build_providers", lambda db: providers)
    out, provider = ai_router.parse_with_fallback(None, "кофе 360", _ctx())
    assert len(out) == 1 and out[0].amount == Decimal("360")
    assert provider == "gigachat"


def test_parse_with_fallback_all_fail_returns_empty(monkeypatch):
    providers = [_FakeProvider("yandex", fail=True), _FakeProvider("gigachat", fail=True)]
    monkeypatch.setattr(ai_router, "build_providers", lambda db: providers)
    entries, provider = ai_router.parse_with_fallback(None, "кофе 360", _ctx())
    assert entries == [] and provider is None


def test_complete_with_fallback(monkeypatch):
    providers = [_FakeProvider("yandex", fail=True), _FakeProvider("gigachat", output="tip")]
    monkeypatch.setattr(ai_router, "build_providers", lambda db: providers)
    text, provider = ai_router.complete_with_fallback(None, "s", "u")
    assert text == "tip" and provider == "gigachat"


def test_provider_label():
    assert ai_router.provider_label("yandex") == "YandexGPT"
    assert ai_router.provider_label("gigachat") == "GigaChat"
    assert ai_router.provider_label(None) == ""
```

- [ ] **Step 2: Run to verify RED**

Run: `.venv/bin/python -m pytest tests/test_ai_router.py -k "fallback or provider_label" -v`
Expected: FAIL (tuple unpack / `provider_label` missing).

- [ ] **Step 3: Update the router**

In `backend/app/services/ai/router.py`, replace `complete_with_fallback` and `parse_with_fallback` and add the label helper:

```python
_PROVIDER_LABELS = {"yandex": "YandexGPT", "gigachat": "GigaChat"}


def provider_label(name: str | None) -> str:
    return _PROVIDER_LABELS.get(name or "", name or "")


def complete_with_fallback(db: Session, system: str, user: str) -> tuple[str | None, str | None]:
    for provider in build_providers(db):
        try:
            return provider.complete(system, user), provider.name
        except AiError as e:
            log.warning("provider %s failed: %s", provider.name, e)
    return None, None


def parse_with_fallback(
    db: Session, text: str, ctx: ParseContext
) -> tuple[list[ParsedEntry], str | None]:
    system, user = build_parse_messages(text, ctx)
    for provider in build_providers(db):
        try:
            raw = provider.complete(system, user)
            return parse_entries(raw), provider.name
        except AiError as e:
            log.warning("provider %s parse failed: %s", provider.name, e)
    return [], None
```

- [ ] **Step 4: Update telegram_bot `_handle_text`**

In `backend/app/services/telegram_bot.py`:

Update the existing router import (line 10) to also import `provider_label`:

```python
from app.services.ai.router import parse_with_fallback, provider_label
```

Replace the body of `_handle_text` from the `entries = ...` line through the final `send_message` (lines 83-97) with:

```python
    entries, provider = parse_with_fallback(db, text, ctx)
    if not entries:
        send_message(token, chat_id, "Не смог разобрать 🤔 Попробуй иначе: «кофе 360, магазин 1560».")
        return

    txs = create_transactions(db, entries, sender)
    _LAST_BATCH[tg_id] = [t.id for t in txs]

    total = sum(t.amount for t in txs)
    lines = [f"✅ {len(txs)} операц. на <b>{float(total):,.0f}".replace(",", " ") + " ₽</b>"]
    for t, e in zip(txs, entries):
        cat = db.get(Category, t.category_id).name if t.category_id else "без категории"
        warn = " ⚠️ проверь" if (e.confidence != "high" or t.category_id is None) else ""
        lines.append(f"• {float(t.amount):,.0f}".replace(",", " ") + f" ₽ — {cat}{warn}")
    if provider:
        lines.append(f"🧠 {provider_label(provider)}")
    send_message(token, chat_id, "\n".join(lines))
```

- [ ] **Step 5: Update daily_digest**

In `backend/app/services/daily_digest.py`:

Add import near the top (with the other `app.services.ai.router` import):

```python
from app.services.ai.router import complete_with_fallback, provider_label
```

Replace `_build_tip` (currently returns `str`) so it returns `(tip, provider)`:

```python
def _build_tip(db: Session, stats: dict) -> tuple[str, str | None]:
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
    tip, provider = complete_with_fallback(db, system, user)
    if tip:
        return tip.strip(), provider
    return random.choice(STATIC_TIPS), None
```

Replace `get_or_build` with a version that stores/shows the provider (add a `_format_digest` helper just above it):

```python
def _format_digest(stats_text: str, tip_text: str, tip_provider: str | None) -> str:
    footer = f"\n🧠 {provider_label(tip_provider)}" if tip_provider else ""
    return f"{stats_text}\n\n💡 {tip_text}{footer}"


def get_or_build(db: Session, today: date | None = None) -> str:
    today = today or date.today()
    key = f"digest.{today.isoformat()}"
    cached = get_setting(db, key, "")
    if cached:
        data = json.loads(cached)
        return _format_digest(data["stats_text"], data["tip_text"], data.get("tip_provider"))

    stats = _collect_stats(db, today)
    stats_text = _stats_text(stats)
    tip_text, tip_provider = _build_tip(db, stats)
    set_setting(
        db,
        key,
        json.dumps(
            {"stats_text": stats_text, "tip_text": tip_text, "tip_provider": tip_provider},
            ensure_ascii=False,
        ),
    )
    return _format_digest(stats_text, tip_text, tip_provider)
```

- [ ] **Step 6: Update daily_digest tests (fakes return tuples)**

In `backend/tests/test_daily_digest.py`, change the three `complete_with_fallback` monkeypatches:

```python
    # test_digest_caches_for_the_day: fake_complete returns a tuple
    def fake_complete(db_, system, user):
        calls["n"] += 1
        return "Совет: копи 10%.", "yandex"
    ...
    # test_digest_falls_back_to_static_tip:
    monkeypatch.setattr(daily_digest, "complete_with_fallback", lambda db_, s, u: (None, None))
    ...
    # test_digest_rebuilds_on_new_day:
    monkeypatch.setattr(daily_digest, "complete_with_fallback", lambda db_, s, u: ("tip", "yandex"))
```

Add an assertion to `test_digest_caches_for_the_day` that the provider footer shows:

```python
    assert "YandexGPT" in first
```

- [ ] **Step 7: Update telegram_bot test fake**

In `backend/tests/test_telegram_bot.py`, the `test_handle_update_writes_transaction` monkeypatch of `parse_with_fallback` must return a tuple now:

```python
    monkeypatch.setattr(
        telegram_bot, "parse_with_fallback",
        lambda d, text, ctx: (
            [ParsedEntry(Decimal("360"), "expense", "Кофе", None, None, "кофе", "high")],
            "yandex",
        ),
    )
```

And extend the assertion to check the provider footer:

```python
    assert sent and "360" in sent[0]
    assert "YandexGPT" in sent[0]
```

- [ ] **Step 8: Run the full suite (GREEN)**

Run: `.venv/bin/python -m pytest -v`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/ai/router.py backend/app/services/telegram_bot.py \
        backend/app/services/daily_digest.py backend/tests/test_ai_router.py \
        backend/tests/test_daily_digest.py backend/tests/test_telegram_bot.py
git commit -m "feat(bot): show which AI provider answered (parse replies + /stats)"
```

---

### Task 3: tg_client — reply_markup + answerCallbackQuery

**Files:**
- Modify: `backend/app/services/tg_client.py:33-38`
- Test: `backend/tests/test_telegram_bot.py` (append)

**Interfaces:**
- `send_message(token, chat_id, text, reply_markup: dict | None = None) -> None` — includes `reply_markup` in the payload only when provided.
- `answer_callback_query(token, callback_query_id, text: str = "") -> None` — best-effort (swallows `TgError`).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_telegram_bot.py`:

```python
def test_send_message_includes_reply_markup(monkeypatch):
    captured = {}

    def handler(request):
        import json as _json
        captured.update(_json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {}})

    monkeypatch.setattr(tg_client, "_client_factory",
                        lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    tg_client.send_message("tok", 1, "hi", reply_markup={"inline_keyboard": []})
    assert captured["reply_markup"] == {"inline_keyboard": []}


def test_answer_callback_query(monkeypatch):
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        return httpx.Response(200, json={"ok": True, "result": {}})

    monkeypatch.setattr(tg_client, "_client_factory",
                        lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    tg_client.answer_callback_query("tok", "cb1", "ok")
    assert seen["path"].endswith("/answerCallbackQuery")
```

- [ ] **Step 2: Run to verify RED**

Run: `.venv/bin/python -m pytest tests/test_telegram_bot.py -k "reply_markup or answer_callback" -v`
Expected: FAIL (`send_message` has no `reply_markup`; `answer_callback_query` missing).

- [ ] **Step 3: Implement**

In `backend/app/services/tg_client.py`, replace `send_message` and add `answer_callback_query`:

```python
def send_message(token: str, chat_id: int | str, text: str, reply_markup: dict | None = None) -> None:
    # Best-effort: log and swallow so a reply failure never breaks the webhook.
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        _call(token, "sendMessage", payload)
    except TgError as e:
        log.warning("sendMessage failed: %s", e)


def answer_callback_query(token: str, callback_query_id: str, text: str = "") -> None:
    try:
        _call(token, "answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})
    except TgError as e:
        log.warning("answerCallbackQuery failed: %s", e)
```

- [ ] **Step 4: Run to verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_telegram_bot.py -k "reply_markup or answer_callback" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tg_client.py backend/tests/test_telegram_bot.py
git commit -m "feat(bot): tg_client reply_markup support + answerCallbackQuery"
```

---

### Task 4: Reply keyboard + button→command mapping

**Files:**
- Modify: `backend/app/services/telegram_bot.py` (constants, `handle_update`, command replies)
- Test: `backend/tests/test_telegram_bot.py`

**Interfaces:**
- Consumes: `send_message(..., reply_markup=...)` (Task 3).
- Produces: incoming button texts `📊 Статистика` / `↩️ Отменить` / `❓ Помощь` behave exactly like `/stats` / `/undo` / `/help`; the commands keyboard is attached to those replies and to the parse reply.

- [ ] **Step 1: Update the existing send_message monkeypatches (so they accept the new kwarg)**

In `backend/tests/test_telegram_bot.py`, every `monkeypatch.setattr(telegram_bot, "send_message", lambda token, chat_id, text: ...)` must accept `reply_markup=None`. Update each to:

```python
    monkeypatch.setattr(telegram_bot, "send_message",
                        lambda token, chat_id, text, reply_markup=None: sent.append(text))
```

(There are such lambdas in `test_handle_update_writes_transaction` and `test_handle_update_rejects_unknown_sender` — update both.)

- [ ] **Step 2: Write the failing test**

Append to `backend/tests/test_telegram_bot.py`:

```python
def test_button_text_triggers_stats(db, monkeypatch):
    _seed_people_and_cats(db)
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "tok")
    monkeypatch.setattr(telegram_bot, "build_digest", lambda d: "ДАЙДЖЕСТ")
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message",
                        lambda token, chat_id, text, reply_markup=None: sent.append(text))
    update = {"message": {"text": "📊 Статистика", "chat": {"id": 111}, "from": {"id": 111}}}
    telegram_bot.handle_update(db, update)
    assert sent == ["ДАЙДЖЕСТ"]
```

- [ ] **Step 3: Run to verify RED**

Run: `.venv/bin/python -m pytest tests/test_telegram_bot.py -k button_text -v`
Expected: FAIL (button text is treated as free-form expense text, not `/stats`).

- [ ] **Step 4: Implement in telegram_bot.py**

Add constants after `_HELP` (around line 28):

```python
_COMMANDS_KB = {
    "keyboard": [["📊 Статистика", "↩️ Отменить", "❓ Помощь"]],
    "resize_keyboard": True,
    "is_persistent": True,
}
_BUTTON_TO_CMD = {
    "📊 Статистика": "/stats",
    "↩️ Отменить": "/undo",
    "❓ Помощь": "/help",
}
```

In `handle_update`, right after `text = (msg.get("text") or "").strip()` (line 40), normalize button text to its command:

```python
        text = _BUTTON_TO_CMD.get(text, text)
```

Attach the keyboard to the command replies — update the three command `send_message` calls:

```python
        if text in ("/start", "/help"):
            send_message(token, chat_id, _HELP, reply_markup=_COMMANDS_KB)
            return
        if text == "/stats":
            send_message(token, chat_id, build_digest(db), reply_markup=_COMMANDS_KB)
            return
```

And in `_handle_undo`, attach it to the confirmation:

```python
def _handle_undo(db, token, chat_id, tg_id) -> None:
    ids = _LAST_BATCH.pop(tg_id, [])
    if not ids:
        send_message(token, chat_id, "Нечего отменять.", reply_markup=_COMMANDS_KB)
        return
    db.query(Transaction).filter(Transaction.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    send_message(token, chat_id, f"↩️ Удалено операций: {len(ids)}.", reply_markup=_COMMANDS_KB)
```

And attach it to the final parse reply in `_handle_text` (the `send_message(token, chat_id, "\n".join(lines))` line):

```python
    send_message(token, chat_id, "\n".join(lines), reply_markup=_COMMANDS_KB)
```

- [ ] **Step 5: Run the full suite (GREEN)**

Run: `.venv/bin/python -m pytest -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/telegram_bot.py backend/tests/test_telegram_bot.py
git commit -m "feat(bot): reply-keyboard buttons for /stats /undo /help"
```

---

### Task 5: Ask category on null via inline buttons + callback_query

**Files:**
- Modify: `backend/app/services/telegram_bot.py` (imports, `_handle_text`, `handle_update`, new helpers)
- Test: `backend/tests/test_telegram_bot.py`

**Interfaces:**
- Consumes: `answer_callback_query` (Task 3), `send_message(..., reply_markup=...)`.
- Produces:
  - `_money(x) -> str` helper (`"1 840"`).
  - `_category_keyboard(db, tx_id) -> dict` — inline keyboard of non-hidden, non-income categories; each button `callback_data = f"setcat:{tx_id}:{cat_id}"`.
  - `_handle_callback(db, cb)` — on `setcat:<tx>:<cat>` sets the transaction's category (whitelist-gated), answers the callback, confirms.
  - `handle_update` routes `update["callback_query"]` to `_handle_callback`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_telegram_bot.py`:

```python
def test_null_category_op_offers_keyboard(db, monkeypatch):
    _seed_people_and_cats(db)
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "tok")
    monkeypatch.setattr(
        telegram_bot, "parse_with_fallback",
        lambda d, text, ctx: (
            [ParsedEntry(Decimal("1840"), "expense", None, None, None, "ремонт газа", "low")],
            "yandex",
        ),
    )
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message",
                        lambda token, chat_id, text, reply_markup=None: sent.append((text, reply_markup)))
    update = {"message": {"text": "ремонт газа 1840", "chat": {"id": 111}, "from": {"id": 111}}}
    telegram_bot.handle_update(db, update)
    # one of the sends carries an inline keyboard with a setcat callback
    kb_sends = [rm for _, rm in sent if rm and "inline_keyboard" in rm]
    assert kb_sends, "expected an inline category keyboard"
    flat = [b for row in kb_sends[0]["inline_keyboard"] for b in row]
    assert any(b["callback_data"].startswith("setcat:") for b in flat)


def test_callback_sets_category(db, monkeypatch):
    _seed_people_and_cats(db)
    from app.models import Transaction, Category
    tx = Transaction(type="expense", amount=Decimal("1840"), date=date.today(), user_id=None)
    db.add(tx); db.commit(); db.refresh(tx)
    cat = db.query(Category).filter_by(name="Кофе").first()
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "tok")
    monkeypatch.setattr(telegram_bot, "answer_callback_query", lambda *a, **k: None)
    monkeypatch.setattr(telegram_bot, "send_message", lambda *a, **k: None)
    update = {"callback_query": {"id": "cb1", "from": {"id": 111},
              "message": {"chat": {"id": 111}}, "data": f"setcat:{tx.id}:{cat.id}"}}
    telegram_bot.handle_update(db, update)
    db.refresh(tx)
    assert tx.category_id == cat.id


def test_callback_rejects_unknown_sender(db, monkeypatch):
    _seed_people_and_cats(db)
    from app.models import Transaction, Category
    tx = Transaction(type="expense", amount=Decimal("500"), date=date.today())
    db.add(tx); db.commit(); db.refresh(tx)
    cat = db.query(Category).filter_by(name="Кофе").first()
    monkeypatch.setattr(telegram_bot, "get_secret", lambda d, k, default="": "tok")
    answered = []
    monkeypatch.setattr(telegram_bot, "answer_callback_query",
                        lambda token, cb_id, text="": answered.append(text))
    monkeypatch.setattr(telegram_bot, "send_message", lambda *a, **k: None)
    update = {"callback_query": {"id": "cb1", "from": {"id": 999},
              "message": {"chat": {"id": 999}}, "data": f"setcat:{tx.id}:{cat.id}"}}
    telegram_bot.handle_update(db, update)
    db.refresh(tx)
    assert tx.category_id is None  # unchanged for a non-whitelisted user
```

- [ ] **Step 2: Run to verify RED**

Run: `.venv/bin/python -m pytest tests/test_telegram_bot.py -k "null_category or callback" -v`
Expected: FAIL (no keyboard offered; `callback_query` not handled).

- [ ] **Step 3: Implement in telegram_bot.py**

Extend the tg_client import (line 13):

```python
from app.services.tg_client import answer_callback_query, send_message
```

Add helpers (after `_sender`):

```python
def _money(x) -> str:
    return f"{float(x):,.0f}".replace(",", " ")


def _category_keyboard(db: Session, tx_id: int) -> dict:
    cats = (
        db.query(Category)
        .filter(Category.is_hidden.is_(False), Category.group != "income")
        .order_by(Category.sort_order, Category.id)
        .all()
    )
    buttons = [{"text": c.name, "callback_data": f"setcat:{tx_id}:{c.id}"} for c in cats]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return {"inline_keyboard": rows}
```

Route callbacks at the very top of `handle_update`'s `try` (before the `msg = ...` line):

```python
    try:
        cb = update.get("callback_query")
        if cb:
            _handle_callback(db, cb)
            return
        msg = update.get("message") or update.get("edited_message")
```

Add the callback handler (near `_handle_undo`):

```python
def _handle_callback(db, cb) -> None:
    token = get_secret(db, "secret.tg_bot_token")
    if not token:
        return
    cb_id = cb["id"]
    tg_id = str(cb["from"]["id"])
    chat_id = cb.get("message", {}).get("chat", {}).get("id", tg_id)
    data = cb.get("data", "")
    if _sender(db, tg_id) is None:
        answer_callback_query(token, cb_id, "Нет доступа")
        return
    if data.startswith("setcat:"):
        try:
            _, tx_s, cat_s = data.split(":")
            tx = db.get(Transaction, int(tx_s))
            cat = db.get(Category, int(cat_s))
        except (ValueError, KeyError):
            answer_callback_query(token, cb_id, "")
            return
        if not tx or not cat:
            answer_callback_query(token, cb_id, "Операция не найдена")
            return
        tx.category_id = cat.id
        db.commit()
        answer_callback_query(token, cb_id, f"✅ {cat.name}")
        send_message(token, chat_id, f"✅ Категория: {cat.name} — {_money(tx.amount)} ₽")
        return
    answer_callback_query(token, cb_id, "")
```

In `_handle_text`, after the summary `send_message(... reply_markup=_COMMANDS_KB)`, offer a category picker for each unresolved op:

```python
    send_message(token, chat_id, "\n".join(lines), reply_markup=_COMMANDS_KB)
    for t, e in zip(txs, entries):
        if t.category_id is None:
            label = e.comment or text
            send_message(
                token, chat_id,
                f"❓ Категория для «{_money(t.amount)} ₽ — {label}»?",
                reply_markup=_category_keyboard(db, t.id),
            )
```

- [ ] **Step 4: Run the full suite (GREEN)**

Run: `.venv/bin/python -m pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/telegram_bot.py backend/tests/test_telegram_bot.py
git commit -m "feat(bot): ask for category via inline buttons when AI leaves it empty"
```

---

## Final verification & deploy (controller)

- [ ] **Full backend suite green**

Run: `.venv/bin/python -m pytest -v` from `backend/`. Expected: all pass.

- [ ] **Deploy note**

No `setWebhook` change needed — Telegram's default `allowed_updates` already delivers `callback_query` to the existing webhook. A digest already cached for *today* (before this deploy) won't have a provider footer until the next calendar day (backward-compatible: `data.get("tip_provider")` → no footer). Push `main` → GitHub Actions autodeploys to the VPS (DNS/cert already live).

- [ ] **Post-deploy smoke (in Telegram)**

Send «ремонт газа 1840» → reply shows `🧠 YandexGPT` and a follow-up «❓ Категория…» with buttons; tap one → «✅ Категория: …». Tap `📊 Статистика` button → digest with a `🧠 …` footer.
