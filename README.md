# Семейный бюджет (fin-home)

Веб-приложение для семейного бюджета по методу **50/30/20**. Данные на вашем VPS, доступ с телефона и браузера.

**Production:** https://194.154.29.93  
**Репозиторий:** https://github.com/avdealex360/fin-home

---

## Быстрый старт

```bash
git clone https://github.com/avdealex360/fin-home.git
cd fin-home
make setup          # .env + data/backups
make up             # Docker → http://127.0.0.1:8000
```

Логин и пароль — из `.env` (`APP_USER`, `APP_PASSWORD`).

Без Docker: `make install && make dev`

---

## Документация

| Документ | Описание |
|----------|----------|
| **[docs/README.md](docs/README.md)** | **Индекс:** с чего начать, чеклист, FAQ |
| **[docs/PROJECT.md](docs/PROJECT.md)** | Архитектура, бизнес-процессы, интерфейс |
| **[docs/DEPLOY.md](docs/DEPLOY.md)** | VPS, GitHub Actions, HTTPS |
| **[docs/MAKEFILE.md](docs/MAKEFILE.md)** | Все команды `make` |

Список команд: `make help`

---

## Возможности

- **Дашборд** — 50/30/20, долги, цели, советы, быстрая запись операций
- **План** — лимиты, плановые крупные расходы и взносы по долгам (любой месяц)
- **Аналитика** — план vs факт, топ категорий, накопительный график
- **Вклад** — калькулятор капитализации, график ставок
- **Цели** — подушка, вклад, машина
- **Настройки** — долги, категории, курсы EUR/RUB, экспорт
- **Telegram** — `/add`, `/income`, `/balance` (опционально)

---

## Стек

Python 3.12 · FastAPI · SQLite · SQLAlchemy · Alembic · HTMX · Jinja2 · Tailwind · Docker · Caddy

---

## Команды

| Задача | Команда |
|--------|---------|
| Локально | `make up` / `make down` / `make logs` |
| Разработка | `make dev` |
| Тесты | `make test` |
| Миграции | `make migrate` |
| Бэкап | `make backup` |
| **VPS prod** | `make prod-up` / `make prod-check` |
| Деплой | `git push origin main` или `make deploy` на сервере |

---

## Деплой на VPS (кратко)

```bash
# root, один раз
make vps-setup

# deploy
make setup && nano .env
make prod-up && make prod-migrate && make prod-check
```

HTTPS: self-signed сертификат (`make prod-certs`). Браузер покажет предупреждение — это нормально.

**GitHub Actions** (автодеплой): нужны Secrets `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` — см. [docs/DEPLOY.md §4](docs/DEPLOY.md#шаг-4-секреты-github).

Подробно: **[docs/DEPLOY.md](docs/DEPLOY.md)** · **[docs/README.md](docs/README.md)**

---

## Первые шаги в интерфейсе

1. **План** — ожидаемый доход, крупные расходы, лимиты (можно на следующий месяц)
2. **Настройки** — проверить долги и категории (предзаполнены)
3. **Дашборд** — вносить операции через «Быструю запись»

Подробный сценарий: **[docs/PROJECT.md §4](docs/PROJECT.md#4-ежемесячный-цикл-бизнес-процесс)**

---

## Telegram (опционально)

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_IDS=123456789
```

Webhook нужен домен с Let's Encrypt. Уведомления: `make notify`.

---

## Бэкап

```bash
make backup          # локально
make prod-backup     # на VPS
```

Cron на VPS:

```
0 3 * * * cd /opt/fin-home && make prod-backup >> /var/log/fin-home-backup.log 2>&1
```

---

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `APP_USER` | Логин Basic Auth |
| `APP_PASSWORD` | Пароль |
| `APP_SECRET` | Секрет приложения |
| `DATABASE_URL` | `sqlite:///./data/budget.db` |
| `TELEGRAM_BOT_TOKEN` | Токен бота (опционально) |
| `TELEGRAM_ALLOWED_IDS` | ID пользователей Telegram |

Пример: [`.env.example`](.env.example)

---

## Переезд на другой VPS

```bash
tar -czf budget-backup.tar.gz data/ .env certs/
scp budget-backup.tar.gz user@new-vps:~/
# на новом VPS:
tar -xzf budget-backup.tar.gz && make prod-up
```
