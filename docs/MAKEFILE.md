# Makefile — шпаргалка по командам

Все команды — из корня репозитория:

```bash
cd fin-home
make help
```

Документация: [PROJECT.md](PROJECT.md) · [DEPLOY.md](DEPLOY.md) · [README.md](../README.md)

---

## Быстрый старт

### Локально (Python)

```bash
make setup && make install && make dev    # http://127.0.0.1:8000
```

### Локально (Docker)

```bash
make setup && make up                     # http://127.0.0.1:8000
make logs && make down
```

### Production (VPS)

```bash
make setup && nano .env
make prod-up                              # certs + Caddy + app
make prod-migrate && make prod-check      # https://194.154.29.93
```

---

## Все команды

| Команда | Описание |
|---------|----------|
| `make help` | Список всех команд |
| **Инициализация** | |
| `make setup` | `.env` из примера + `data/backups/` |
| `make install` | `pip install -r requirements.txt` |
| **Локальная разработка** | |
| `make dev` | Uvicorn hot-reload `:8000` |
| `make test` | pytest (`pip install pytest`) |
| `make migrate-local` | Alembic без Docker |
| `make notify` | Telegram-уведомления |
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
| `make prod-migrate` | Миграции |
| `make prod-migrate-stamp` | Stamp head |
| `make prod-check` | Диагностика HTTPS |
| `make prod-caddy-reset` | Сброс Caddy + перезапуск |
| `make prod-backup` | Бэкап на сервере |
| **VPS** | |
| `make deploy` | `scripts/deploy.sh` |
| `make install-compose` | Docker Compose (root) |
| `make vps-setup` | Первичная настройка VPS (root) |

---

## Типичные сценарии

### Первый запуск локально

```bash
make setup
# отредактировать .env
make up
open http://127.0.0.1:8000
```

### Обновление после git pull (локально)

```bash
make rebuild && make migrate
```

### Первый запуск на VPS

```bash
make vps-setup                    # root
make setup && nano .env           # deploy
make prod-up && make prod-migrate && make prod-check
```

### Деплой новой версии

- Авто: `git push origin main`
- Вручную на VPS: `make deploy` или `make prod-rebuild && make prod-migrate`

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
PYTHON=.venv/bin/python make dev
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
| `make notify` | `scripts/notify.py` |

---

## ⚠ На VPS

| Делать | Не делать |
|--------|-----------|
| `make prod-up` | `make up` (без Caddy) |
| `make prod-rebuild` | `make rebuild` |
| `make prod-check` | — |
| `make deploy` | — |
