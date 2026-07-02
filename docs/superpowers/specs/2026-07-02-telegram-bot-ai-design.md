# Telegram-бот с AI-разбором трат — дизайн

**Дата:** 2026-07-02
**Статус:** согласован, готов к плану реализации

## Цель

Добавить Telegram-бота, который принимает свободный текст на русском
(«Магазин продуктовый 1560 руб, кофе взял за 360, и оплатил интернет 1200»),
разбирает его через российские LLM (YandexGPT / GigaChat, бесплатные тарифы,
с fallback между ними) и **сразу** записывает распознанные операции в бюджет —
в существующие категории и на существующих людей (Леша / Катя / Общее).
Правки при ошибке распознавания делаются вручную в UI приложения.

Параллельно — перевод всего приложения с self-signed-сертификата по IP на
домен `lunalis.tech` с Let's Encrypt (нужен для webhook и заодно даёт красивый
адрес входа).

## Ключевые решения (согласованы с заказчиком)

1. **Режим бота: webhook** (не long polling). Telegram шлёт апдейты POST-запросом
   на публичный HTTPS-эндпоинт. Следствие: бот — это просто FastAPI-роут, без
   постоянно живущего процесса, без aiogram-поллинга, без фоновых asyncio-задач.
2. **Запись сразу** (без inline-подтверждения). Бот создаёт операции немедленно,
   при неуверенности помечает их в ответе (`⚠️ проверь`). Исправление — в UI.
3. **Человек — по отправителю Telegram.** `telegram_id` привязан к `AppUser`.
   Если текст явно называет другого человека или «общее» — AI переопределяет.
4. **Ключи — в UI приложения** (новый раздел «Интеграции»), хранятся в БД
   (таблица `settings`, префикс `secret.*`), маскируются, исключены из экспорта.
5. **Весь app переезжает на `https://lunalis.tech`** с Let's Encrypt через Caddy.
6. **Дата — из текста.** AI понимает «вчера / позавчера / N дней назад / в
   понедельник» относительно переданной сегодняшней даты; если не упомянута — сегодня.
7. **Команда `/stats`** — статистика + «совет дня». Совет: **случайная ротация**
   каждый день между двумя режимами AI — (а) персональный на основе статистики,
   (б) тематический по фин-грамотности; при недоступности AI — статичный из списка.
   Дайджест **кэшируется на календарный день**: первый запрос строит и сохраняет,
   остальные за день получают тот же.
8. Осознанные упрощения: без aiogram (тонкий httpx-клиент); `/undo` живёт только
   в памяти процесса (не переживает рестарт — приемлемо для семейного бота).

## Архитектура

Всё внутри существующего контейнера `budget-app`. Новых сервисов/контейнеров нет.

```
backend/app/
  api/telegram.py              — POST /api/tg/webhook/{secret}  (публичный, вне session-auth)
  services/
    telegram_bot.py            — оркестрация: whitelist, команды, запись, ответ
    tg_client.py               — тонкий httpx-клиент Telegram Bot API (sendMessage, setWebhook, getMe)
    tx_resolver.py             — ParsedEntry -> category_id/user_id -> Transaction
    daily_digest.py            — /stats: сбор статы + «совет дня», кэш на день
    ai/
      base.py                  — интерфейс AiProvider (parse + complete) + ParsedEntry + промпты
      yandex.py                — YandexGPT (Api-Key + folder_id)
      gigachat.py              — GigaChat (OAuth client-credentials, кэш токена ~30 мин)
      router.py                — fallback-цепочка primary -> secondary (parse и complete)
```

### Поток обработки апдейта

1. Telegram → `POST /api/tg/webhook/{secret}`.
   Проверка: секрет в пути **и** заголовок `X-Telegram-Bot-Api-Secret-Token`.
   Несовпадение → `403`.
2. Извлекаем `from.id`, `text`. Whitelist: `from.id` должен быть в `AppUser.telegram_id`
   среди активных. Иначе — вежливый отказ, ничего не пишем.
3. Команды: `/start`, `/help` → справка (и `from.id` для привязки); `/undo` →
   удалить операции последней пачки этого `telegram_id`; `/stats` → дневной
   дайджест (см. раздел «Статистика и совет дня»).
4. Обычный текст → `ai.router.parse(text, context)` → `list[ParsedEntry]`.
5. Резолв каждого entry (`tx_resolver`):
   - **person**: из `entry.person`, иначе — `AppUser` отправителя;
   - **category**: точное совпадение по имени → нечёткое → нет уверенного →
     `category_id = null` + пометка в комментарии;
   - **date**: `entry.date` (уже ISO от AI), иначе сегодня;
   - **type**: `entry.type` (income/expense), по умолчанию expense.
6. Создаём `Transaction` сразу. Запоминаем id пачки в памяти процесса
   (`dict[telegram_id] -> list[tx_id]`) для `/undo`.
7. Ответ-итог: `✅ 3 операции на 3120 ₽` + построчная разбивка. Строки с
   `confidence != "high"` или нераспознанной категорией → `⚠️ проверь`.

### Webhook и session-auth

`/api/tg/webhook` добавляется в `_PUBLIC_API_PREFIXES` в `main.py` (сейчас строка 60),
чтобы миддлварь `require_session` его не резала. Защита — не session-cookie, а
секретный путь + secret-token Telegram.

## Модель данных

Одна миграция Alembic (`backend/alembic/versions/`).

- `AppUser.telegram_id: Mapped[str | None]`, `nullable=True`, `unique=True`.
  Привязка человека к аккаунту Telegram; она же — whitelist доступа к боту.

Настройки и секреты — в существующей `Setting` (key/value), без новой таблицы:

| ключ                     | назначение                                  | секрет |
|--------------------------|---------------------------------------------|--------|
| `secret.tg_bot_token`    | токен бота от @BotFather                     | да     |
| `secret.tg_webhook_secret` | секрет пути/заголовка webhook (генерится)  | да     |
| `secret.yandex_api_key`  | API-ключ сервисного аккаунта Yandex Cloud    | да     |
| `secret.yandex_folder_id`| folder id Yandex Cloud                       | да     |
| `secret.gigachat_auth_key`| Authorization key GigaChat (base64 client)  | да     |
| `ai_primary_provider`    | `yandex` \| `gigachat` (по умолчанию yandex) | нет    |
| `tg_bot_enabled`         | `1` \| `` — общий тумблер                    | нет    |

### Безопасность секретов

- В `DEFAULT_SETTINGS` (`seed.py`) добавляются только несекретные ключи
  (`ai_primary_provider=yandex`, `tg_bot_enabled=""`). Секреты не сидятся.
- `GET /api/settings` и `export_json` (`settings.py`) **фильтруют** ключи с
  префиксом `secret.*`: в экспорт не попадают вообще; в GET интеграций отдаются
  маской (`••••1234`, последние 4 символа) либо флагом «задан/не задан».
- Запись секрета — только при непустом вводе (пустое поле = «не менять»).
- Хелперы `get_secret(db, key)` / `set_secret(db, key, value)` поверх
  `settings_store` (тонкая обёртка, единая точка чтения секретов).

## AI-разбор — контракт

Общий интерфейс:

```python
@dataclass
class ParsedEntry:
    amount: Decimal
    type: str            # "expense" | "income"
    category: str | None # имя категории как его вернул AI
    person: str | None   # имя человека / "общее" / None
    date: date | None    # уже вычисленная ISO-дата или None
    comment: str | None
    confidence: str      # "high" | "low"

class AiProvider(Protocol):
    name: str
    def complete(self, system: str, user: str) -> str: ...   # базовый вызов LLM
    def parse(self, text: str, ctx: ParseContext) -> list[ParsedEntry]: ...  # поверх complete
    def healthcheck(self) -> bool: ...
```

`parse` и «совет дня» строятся поверх единого `complete(system, user)`; router
даёт `parse_with_fallback` и `complete_with_fallback` с одной и той же цепочкой.

`ParseContext` содержит: список категорий (`id, name, group`), список людей,
имя отправителя, сегодняшнюю дату (ISO), валюту.

**Промпт** (единый для обоих провайдеров) требует строгий JSON:

```json
{"entries":[
  {"amount":1560,"type":"expense","category":"Продукты и быт",
   "person":null,"date":null,"comment":"магазин","confidence":"high"}
]}
```

Правила в промпте: суммы — числом без пробелов/валюты; категорию выбирать строго
из переданного списка (иначе `null`); относительные даты («вчера», «позавчера»,
«N дней назад», «в понедельник») вычислять от сегодняшней даты в ISO, иначе `null`;
доходы (зарплата, поступление) → `type=income`; неуверенность → `confidence=low`.

### Fallback-цепочка (`router.py`)

1. Определить порядок: `ai_primary_provider` первым, второй — резервным.
2. Вызвать первого. Успех (валидный JSON, ≥1 entry) → вернуть.
3. Ошибка/quota (429/401/5xx/таймаут/невалидный JSON) → лог + второй провайдер.
4. Оба легли → вернуть пустой список; бот отвечает «не смог разобрать».

- **GigaChat**: OAuth `POST /api/v2/oauth` с `Authorization: Basic <auth_key>` →
  access token (TTL ~30 мин, кэшируем в памяти по времени истечения);
  затем `POST /chat/completions`.
- **YandexGPT**: `POST .../foundationModels/v1/completion`,
  заголовок `Authorization: Api-Key <key>`, `modelUri=gpt://<folder_id>/yandexgpt-lite`.
- httpx-таймаут ~15 c на провайдера.

## Статистика и совет дня (`/stats`)

`services/daily_digest.py` — `get_or_build(db) -> str`:

1. Ключ кэша `digest.<YYYY-MM-DD>` в `Setting` (JSON: `stats_text`, `tip_text`,
   `tip_mode`). Если запись за сегодня есть → вернуть её (кэш «на всех, на день»).
2. Иначе **собрать статистику** из существующих сервисов (`dashboard.py`,
   `analytics.py`, `pair_analytics.py`) — без AI:
   - траты за текущий месяц и остаток до конца плана;
   - топ-категория месяца;
   - фактический сплит 50/30/20 (needs/wants/savings) vs целевой;
   - сравнение с прошлым месяцем (± %);
   - разбивка по людям (Леша/Катя/Общее).
3. **Совет дня — случайная ротация** режима на день:
   - `random.choice(["stats", "literacy"])`;
   - `stats` → `ai.complete_with_fallback(system, user)` с агрегатами из п.2,
     просим короткий персональный совет по цифрам;
   - `literacy` → тот же `complete`, но просим общий совет по фин-грамотности на
     случайную тему (подушка, проценты, импульсивные траты, правило 50/30/20, …);
   - AI недоступен (оба провайдера легли) → `random.choice(STATIC_TIPS)` из
     курируемого списка в коде.
4. Сохранить JSON в `Setting` и вернуть отформатированный текст.

Кэш — снапшот на момент первого запроса за день (согласовано). Старые записи
`digest.*` можно чистить лениво (при построении нового удалять записи прошлых дат)
либо оставить — их немного.

## Настройки в UI

Новый экран **«Интеграции»** — карточка в `More.svelte`, отдельный компонент/маршрут.

- Поля секретов (маскированные, плейсхолдер «задан ••••1234» если уже есть):
  токен бота, Yandex API-ключ, Yandex folder id, GigaChat auth key.
- Выбор `ai_primary_provider` (радио yandex/gigachat).
- Тумблер `tg_bot_enabled`.
- **«Проверить»** → `POST /api/settings/integrations/test`: `getMe` бота +
  `healthcheck` обоих AI-провайдеров, показывает статус каждого.
- **«Переустановить webhook»** → `POST /api/settings/integrations/set-webhook`:
  дёргает `setWebhook` на `{APP_BASE_URL}/api/tg/webhook/{secret}` с secret-token.
- Привязка `telegram_id` к людям: поле у каждого `AppUser` (здесь же или на экране
  управления людьми). Значение можно узнать из ответа бота на `/start`
  (бот сообщает `from.id`).

`frontend/src/lib/api.ts` пополняется типами и вызовами; TS-интерфейсы держим в
синхроне с сериализаторами (конвенция проекта).

## Деплой: домен, сертификат, webhook

- **Caddyfile**: заменить блок `:443 { tls /certs/... }` на:
  ```
  lunalis.tech {
      reverse_proxy budget-app:8000
  }
  ```
  Caddy сам выпустит и продлит Let's Encrypt (нужен открытый `:80` для ACME).
  Весь app и логин доступны по `https://lunalis.tech`. Self-signed по IP убираем
  (или оставляем отдельным блоком как резерв — по желанию).
- **DNS** (руками, в гайде): `A  lunalis.tech  ->  194.154.29.93`.
- **docker-compose.prod.yml**: у caddy уже проброшены `:80`/`:443` — том `./certs`
  для self-signed больше не обязателен; Caddy хранит ACME-сертификаты в
  `caddy_data`. Добавить в env приложения `APP_BASE_URL`.
- **.env / .env.example**: `APP_BASE_URL=https://lunalis.tech`.
- Автодеплой (`git push origin main` → Actions → `scripts/deploy.sh`) не меняем.
- CORS в `main.py` не трогаем (домен = тот же origin, что и SPA).

## Документация

- **`docs/telegram-bot-setup.md`** — пошаговый гайд:
  1. @BotFather: создать бота, получить токен, задать имя/описание.
  2. DNS: A-запись `lunalis.tech → 194.154.29.93`, дождаться распространения.
  3. Деплой с новым Caddyfile, проверить выпуск Let's Encrypt.
  4. YandexGPT: создать folder + сервисный аккаунт в Yandex Cloud, роль
     `ai.languageModels.user`, API-ключ; взять folder id.
  5. GigaChat: получить Authorization key (Сбер, client id/secret → base64).
  6. Вход в приложение → «Интеграции»: вставить ключи, выбрать провайдера,
     включить бота, «Проверить», «Переустановить webhook».
  7. Привязать людей: каждый шлёт боту `/start`, вписать `telegram_id`.
  8. Команды бота: свободный текст (запись трат), `/stats` (статистика + совет
     дня), `/undo`, `/help`.
  9. Отладка: где смотреть логи webhook, частые ошибки (403 webhook, 401 AI,
     quota → fallback, нераспознанная категория).
- **`CLAUDE.md`**: короткий раздел про бота (эндпоинт, сервисы, где ключи).

## Тестирование

`backend/tests/`:

- `tx_resolver`: имя категории → id (точное/нечёткое/нет совпадения → null);
  person из текста vs по отправителю.
- `ai/router`: мок обоих провайдеров — успех primary; quota primary → switch на
  secondary; оба падают → пустой список.
- Парсинг JSON-ответа AI (валидный / мусор / частично валидный).
- Дата: «вчера/позавчера/N дней назад» → корректная ISO; без даты → сегодня.
- Фильтрация `secret.*` в `GET /api/settings` и `export_json`.
- Webhook: неверный секрет/заголовок → 403; неизвестный `telegram_id` → отказ.
- `daily_digest`: первый вызов строит и пишет кэш; повторный за тот же день —
  тот же текст без второго вызова AI (мок `complete`); AI недоступен → статичный
  совет; смена даты → пересборка.

## Вне рамок (YAGNI)

- Голосовые сообщения, фото чеков, OCR.
- Редактирование операций из Telegram (правки — в UI).
- Персистентный `/undo` через БД.
- Автопуш дайджеста по расписанию (планировщик/cron) — `/stats` только по команде;
  расширенная аналитика/отчёты в боте сверх дневного дайджеста.
- Мультивалютный разбор (берём валюту из настроек).
