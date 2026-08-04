# Документация fin-home

Центральный указатель. Начните с [README.md](../README.md), если нужен быстрый старт.

**Production:** https://194.154.29.93

> **v3:** Svelte 5 SPA + FastAPI JSON API. Интерфейс — одностраничное PWA-приложение с hash-роутингом (`#/plan`).

---

## Карта документов

| Документ | Для кого | Содержание |
|----------|----------|------------|
| [README.md](../README.md) | Все | Быстрый старт, ссылки, краткий обзор |
| [PROJECT.md](PROJECT.md) | Пользователи | Бизнес-процессы, интерфейс, архитектура, данные |
| [DEPLOY.md](DEPLOY.md) | DevOps | VPS, Docker, HTTPS, GitHub Actions, troubleshooting |
| [MAKEFILE.md](MAKEFILE.md) | Разработка | Все команды `make` |
| [telegram-bot-setup.md](telegram-bot-setup.md) | Настройка | Бот: токен, webhook, AI-ключи, привязка людей |
| [usdc-wallet-setup.md](usdc-wallet-setup.md) | Настройка | Кошелёк USDC: адрес, ключ Etherscan, порог уведомления |

---

## С чего начать

### Я хочу пользоваться приложением

1. Откройте https://194.154.29.93 (логин из `.env` на сервере, пароль — тот, от которого сгенерирован `APP_PASSWORD_HASH`).
2. Прочитайте [PROJECT.md §4](PROJECT.md#4-ежемесячный-цикл-бизнес-процесс) — ежемесячный цикл.
3. Заполните **План** → вносите операции через **+** на главной.

### Я хочу запустить локально

**UI-разработка (hot-reload):**

```bash
git clone https://github.com/avdealex360/fin-home.git
cd fin-home
make install
make dev-api    # терминал 1
make dev-web    # терминал 2
```

→ http://127.0.0.1:5173

**Docker (как на prod, без hot-reload UI):**

```bash
git clone https://github.com/avdealex360/fin-home.git
cd fin-home
make setup && make up
```

→ http://127.0.0.1:8000

Подробнее: [MAKEFILE.md](MAKEFILE.md)

### Я настраиваю VPS с нуля

1. [DEPLOY.md §1–2](DEPLOY.md#шаг-1-подготовка-vps-один-раз) — `make vps-setup`, `.env`, `make hash-password`, `make prod-up`
2. [DEPLOY.md §3–4](DEPLOY.md#шаг-3-ssh-ключ-для-github-actions) — SSH-ключ и GitHub Secrets
3. [DEPLOY.md §5](DEPLOY.md#шаг-5-автодеплой) — проверка Actions

### Я пушу код и жду автодеплой

1. Убедитесь, что заданы Secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`  
   → https://github.com/avdealex360/fin-home/settings/secrets/actions
2. `git push origin main`
3. GitHub → **Actions** → workflow **Deploy** должен быть зелёным
4. На VPS: `make prod-check`

---

## Чеклист production

- [ ] VPS: `make vps-setup` (root)
- [ ] `.env`: `APP_USER`, `APP_PASSWORD_HASH` (через `make hash-password p=…`), `APP_SECRET` (deploy)
- [ ] `make prod-up && make prod-check`
- [ ] https://194.154.29.93 открывается (401 без логина = OK)
- [ ] SSH-ключ deploy в `authorized_keys`
- [ ] GitHub Secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`
- [ ] Push в `main` → Actions зелёный
- [ ] Cron бэкапа: `make prod-backup`

---

## FAQ

**Браузер ругается на сертификат**  
Нормально для IP без домена. Self-signed cert из `make prod-certs`. Нажмите «Продолжить».

**`missing server host` в GitHub Actions**  
Не задан Secret `VPS_HOST`. См. [DEPLOY.md §4](DEPLOY.md#шаг-4-секреты-github).

**На VPS использовал `make rebuild` — пропал HTTPS**  
`make rebuild` — локальный compose без Caddy. Запустите `make prod-rebuild && make prod-check`.

**Как спланировать следующий месяц?**  
План → стрелки ← → для переключения месяца.

**Где крупные расходы?**  
Только в **Плане** (плановые расходы). FAB **+** — для фактических операций и распределения дохода.

**Чем копилка отличается от вклада?**  
Копилка — расходуемый конверт («Ещё» → Копилки). «Калькулятор вклада» — только расчёт капитализации, на бюджет не влияет; реальное пополнение вклада пишется как обычный расход в категории сбережений. Подробнее: `#/faq`.

**Как посмотреть все операции за период?**  
«Ещё» → «Все операции»: фильтры по типу/категории/участнику и по диапазону дат («С» / «По»).

**Что делает «Закрыть месяц»?**  
В «Плане» внизу. Неизрасходованный остаток каждого лимита (лимит − траты) переносится на следующий месяц. Спрашивает подтверждение, действие необратимо.

**Как включить баланс кошелька USDC и уведомление о зарплате?**  
«Ещё» → «Телеграм-бот, AI и кошелёк» → блок «Кошелёк USDC»: адрес, ключ Etherscan, порог. Дальше баланс виден по тапу на большое число на Главной, а бот раз в месяц напишет, когда баланс превысит порог. Подробно: [usdc-wallet-setup.md](usdc-wallet-setup.md).

**Первый запуск — пустой экран?**  
Онбординг предложит загрузить демо-данные или начать с чистого листа. БД изначально пустая.

**Где данные?**  
`/opt/fin-home/data/budget.db` на VPS. Не в git, не в Docker-образе.

**Как сделать бэкап?**  
`make prod-backup`. Файлы в `data/backups/budget_YYYYMMDD.sql`.

**Нужен ли `make prod-migrate` после деплоя?**  
Нет — миграции Alembic применяются автоматически при старте приложения. Команда остаётся для ручного запуска.

---

## Структура `docs/`

```
docs/
├── README.md      ← этот файл (индекс)
├── PROJECT.md     ← приложение и бизнес-процессы
├── DEPLOY.md      ← VPS и CI/CD
├── MAKEFILE.md    ← команды make
├── telegram-bot-setup.md  ← бот: токен, webhook, AI
├── usdc-wallet-setup.md   ← кошелёк USDC: Etherscan и порог
├── plan.md        ← архив: исходный план разработки
└── superpowers/   ← архив: спеки и планы редизайна v3
```

Архив редизайна v3: [superpowers/specs/2026-06-30-fin-redesign-design.md](superpowers/specs/2026-06-30-fin-redesign-design.md)
