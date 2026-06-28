# Makefile — шпаргалка по командам

Все команды запускаются из корня репозитория:

```bash
cd fin-home
make help
```

---

## Быстрый старт

### Локально (Python)

```bash
make setup      # .env + data/backups
make install    # pip install
make dev        # http://127.0.0.1:8000
```

### Локально (Docker)

```bash
make setup
make up         # http://127.0.0.1:8000
make logs       # смотреть логи
make down       # остановить
```

### Production на VPS

```bash
make setup
make prod-up    # https://194.154.29.93
make prod-migrate
make prod-logs
```

Подробнее про VPS: [DEPLOY.md](DEPLOY.md).

---

## Все команды

| Команда | Описание |
|---------|----------|
| `make help` | Список всех команд |
| **Инициализация** | |
| `make setup` | Создать `.env` из примера и `data/backups/` |
| `make install` | Установить Python-зависимости |
| **Локальная разработка** | |
| `make dev` | Uvicorn с hot-reload на `:8000` |
| `make test` | Запустить pytest |
| `make migrate-local` | Alembic-миграции без Docker |
| `make notify` | Telegram-уведомления (`scripts/notify.py`) |
| **Docker (локально)** | |
| `make up` | Поднять `docker compose up -d --build` |
| `make down` | Остановить контейнеры |
| `make restart` | Перезапустить |
| `make rebuild` | Пересобрать образы и пересоздать контейнеры |
| `make logs` | Логи (follow) |
| `make ps` | Статус контейнеров |
| `make shell` | Bash в контейнере `budget-app` |
| `make migrate` | Миграции внутри Docker |
| `make migrate-stamp` | `alembic stamp head` (если таблицы уже есть) |
| `make backup` | SQL-дамп базы в `data/backups/` |
| **Docker (production)** | |
| `make prod-up` | Prod: Caddy + app (`docker-compose.prod.yml`) |
| `make prod-down` | Остановить prod-стек |
| `make prod-restart` | Перезапустить prod |
| `make prod-rebuild` | Пересобрать prod |
| `make prod-logs` | Логи prod |
| `make prod-ps` | Статус prod-контейнеров |
| `make prod-shell` | Shell в prod-контейнере |
| `make prod-migrate` | Миграции в prod |
| `make prod-migrate-stamp` | Stamp head в prod |
| `make prod-backup` | Бэкап на сервере |
| **VPS** | |
| `make deploy` | Запуск `scripts/deploy.sh` (на сервере) |
| `make install-compose` | Установить Docker Compose plugin (root) |
| `make vps-setup` | Первичная настройка VPS (root) |

---

## Типичные сценарии

### Первый запуск на Mac/Linux

```bash
cp .env.example .env   # или make setup
# отредактировать APP_USER, APP_PASSWORD
make up
open http://127.0.0.1:8000
```

### Обновление после git pull (локально)

```bash
make rebuild
make migrate
```

### Первый запуск на VPS

```bash
# от root
make vps-setup

# от deploy
cd /opt/fin-home
make setup
nano .env
make prod-up
make prod-migrate
```

Если миграции падают с `table app_users already exists`:

```bash
make prod-migrate-stamp
```

### Деплой новой версии

**Автоматически:** `git push origin main` → GitHub Actions.

**Вручную на VPS:**

```bash
make deploy
# или
make prod-rebuild && make prod-migrate
```

### Бэкап и восстановление

```bash
make backup
# или на VPS:
make prod-backup
```

Cron на VPS:

```
0 3 * * * cd /opt/fin-home && make prod-backup >> /var/log/fin-home-backup.log 2>&1
```

Восстановление:

```bash
sqlite3 data/budget.db < data/backups/budget_YYYYMMDD.sql
```

### Docker Compose не установлен на VPS

```bash
# от root
make install-compose
docker compose version
```

---

## Переменные

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `PYTHON` | `python3` | Интерпретатор Python |
| `UVICORN` | `uvicorn` | Команда uvicorn |
| `APP_DIR` | текущая директория | Корень проекта (для deploy.sh) |

Пример:

```bash
PYTHON=.venv/bin/python make dev
```

---

## Соответствие скриптам

| Make | Скрипт / команда |
|------|------------------|
| `make deploy` | `scripts/deploy.sh` |
| `make backup` | `scripts/backup.sh` |
| `make vps-setup` | `scripts/vps-setup.sh` |
| `make install-compose` | `scripts/install-compose.sh` |
| `make notify` | `scripts/notify.py` |

Скрипты можно вызывать напрямую — Makefile это обёртка для удобства.
