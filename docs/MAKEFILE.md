# Makefile — шпаргалка по командам

Все команды — из корня репозитория:

```bash
cd fin-home
make help
```

Документация: [README.md](README.md) · [PROJECT.md](PROJECT.md) · [DEPLOY.md](DEPLOY.md) · [README.md](../README.md)

---

## Быстрый старт

### Локально (Python + Vite, два терминала)

```bash
make setup && make install
make dev-api    # терминал 1 → http://127.0.0.1:8000
make dev-web    # терминал 2 → http://127.0.0.1:5173
```

`make dev` — алиас для `make dev-api` (только backend).

### Локально (Docker)

```bash
make setup && make up                     # http://127.0.0.1:8000
make logs && make down
```

Backend отдаёт собранный SPA; hot-reload frontend недоступен — для UI-разработки используйте `dev-web`.

### Production (VPS)

```bash
make setup && nano .env
make hash-password p=ваш-пароль           # → APP_PASSWORD_HASH в .env
make prod-up                              # certs + Caddy + app
make prod-check                           # https://194.154.29.93
```

Миграции применяются автоматически при старте приложения. `make prod-migrate` — для ручного запуска.

---

## Все команды

| Команда | Описание |
|---------|----------|
| `make help` | Список всех команд |
| **Инициализация** | |
| `make setup` | `.env` из примера + `data/backups/` |
| `make install` | Backend venv через `uv` + `npm install` в frontend |
| `make hash-password p=…` | bcrypt-хэш пароля для Caddy Basic Auth |
| **Локальная разработка** | |
| `make dev-api` | Uvicorn hot-reload `:8000` |
| `make dev-web` | Vite dev `:5173`, прокси `/api` → `:8000` |
| `make dev` | Алиас для `dev-api` |
| `make test` | pytest в backend |
| `make migrate-local` | Alembic без Docker |
| **Docker (локально)** | |
| `make up` | Поднять контейнеры |
| `make down` | Остановить |
| `make restart` | Перезапустить |
| `make rebuild` | Пересобрать (⚠ не на VPS) |
| `make logs` | Логи follow |
| `make ps` | Статус |
| `make shell` | Bash в budget-app |
| `make migrate` | Миграции в Docker |
| `make migrate-stamp` | `alembic stamp head` |
| `make backup` | SQL-дамп в `data/backups/` |
| **Docker (production)** | |
| `make prod-certs` | Self-signed сертификат для IP |
| `make prod-up` | certs + Caddy + app |
| `make prod-down` | Остановить prod |
| `make prod-restart` | Перезапустить |
| `make prod-rebuild` | Пересобрать prod |
| `make prod-logs` | Логи prod |
| `make prod-ps` | Статус контейнеров |
| `make prod-shell` | Shell в budget-app |
| `make prod-migrate` | Миграции вручную (обычно не нужны — auto на старте) |
| `make prod-migrate-stamp` | Stamp head |
| `make prod-check` | Диагностика HTTPS |
| `make prod-caddy-reset` | Сброс Caddy + перезапуск |
| `make prod-backup` | Бэкап на сервере |
| **VPS** | |
| `make deploy` | `scripts/deploy.sh` (git pull + rebuild + health check) |
| `make install-compose` | Docker Compose plugin (root) |
| `make vps-setup` | Первичная настройка VPS (root) |

---

## Типичные сценарии

### Первый запуск локально (UI-разработка)

```bash
make setup && make install
make dev-api    # терминал 1
make dev-web    # терминал 2
open http://127.0.0.1:5173
```

### Первый запуск локально (Docker)

```bash
make setup && make up
open http://127.0.0.1:8000
```

### Обновление после git pull (локально, Docker)

```bash
make rebuild
# миграции применятся при следующем старте контейнера; или:
make migrate
```

### Первый запуск на VPS

```bash
make vps-setup                    # root
make setup && nano .env           # deploy: APP_USER, APP_PASSWORD_HASH, APP_SECRET
make hash-password p=…            # сгенерировать хэш
make prod-up && make prod-check
```

### Деплой новой версии

**Предварительно:** GitHub Secrets `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` ([DEPLOY.md §4](DEPLOY.md#шаг-4-секреты-github))

- **Авто:** `git push origin main` → проверить Actions
- **Вручную на VPS:** `make deploy` или `make prod-rebuild`
- **Проверка:** `make prod-check`

Скрипт `deploy.sh` выполняет `git fetch/reset`, `docker compose up -d --build` и `prod-check`. Отдельный `prod-migrate` не вызывается — миграции на старте приложения.

### HTTPS не работает на VPS

```bash
rm -rf certs/
make prod-certs
make prod-rebuild
make prod-check
curl -Ik https://194.154.29.93 --insecure
```

### Бэкап

```bash
make backup           # локально
make prod-backup      # VPS
```

Cron:

```
0 3 * * * cd /opt/fin-home && make prod-backup >> /var/log/fin-home-backup.log 2>&1
```

Восстановление:

```bash
sqlite3 data/budget.db < data/backups/budget_YYYYMMDD.sql
```

### Docker Compose не установлен

```bash
make install-compose    # root
docker compose version
```

---

## Переменные окружения make

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `PYTHON` | `python3` | Интерпретатор |
| `UVICORN` | `uvicorn` | Сервер разработки |
| `APP_DIR` | `.` | Корень проекта |
| `VPS_IP` | `194.154.29.93` | IP для `gen-certs.sh` |

Пример:

```bash
VPS_IP=203.0.113.10 make prod-certs
```

---

## Скрипты

| Make | Скрипт |
|------|--------|
| `make deploy` | `scripts/deploy.sh` |
| `make backup` | `scripts/backup.sh` |
| `make prod-check` | `scripts/prod-check.sh` |
| `make prod-certs` | `scripts/gen-certs.sh` |
| `make vps-setup` | `scripts/vps-setup.sh` |
| `make install-compose` | `scripts/install-compose.sh` |

---

## ⚠ На VPS

| Делать | Не делать |
|--------|-----------|
| `make prod-up` | `make up` (без Caddy) |
| `make prod-rebuild` | `make rebuild` |
| `make prod-check` | — |
| `make deploy` | — |
