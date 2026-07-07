.DEFAULT_GOAL := help

SHELL := /bin/bash

APP_DIR ?= $(CURDIR)
COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
COMPOSE_LOCAL := $(COMPOSE) -f docker-compose.yml
COMPOSE_PROD := $(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml
PYTHON ?= python3
UVICORN ?= uvicorn

.PHONY: help setup install dev test \
        up down restart rebuild logs ps shell db-ui \
        prod-up prod-down prod-restart prod-rebuild prod-rebuild-nocache prod-logs prod-ps prod-shell \
        prod-migrate prod-migrate-stamp prod-backup prod-check prod-caddy-reset prod-certs prod-verify prod-tail-ai \
        migrate migrate-local migrate-stamp \
        backup deploy install-compose vps-setup

help: ## Показать все команды
	@grep -E '^[a-zA-Z0-9_-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- Инициализация ---

setup: ## Создать .env (если нет) и каталог data/backups
	@test -f .env || cp .env.example .env
	@mkdir -p data/backups
	@echo "OK: .env и data/backups готовы"

install: setup ## Установить зависимости backend (venv через uv) и frontend
	cd backend && uv venv --python 3.12 .venv && uv pip install --python .venv -r requirements.txt
	cd frontend && npm install

# --- Локальная разработка (без Docker) ---
# Запускать в двух терминалах: `make dev-api` и `make dev-web`.

dev-api: setup ## Backend API с hot-reload на :8000
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-web: ## Frontend (Vite) на :5173, проксирует /api на :8000
	cd frontend && npm run dev

dev: dev-api ## Алиас для dev-api

test: ## Запустить тесты backend
	cd backend && .venv/bin/python -m pytest tests/ -v

hash-password: ## Сгенерировать bcrypt-хэш пароля для Caddy basic_auth
	@docker run --rm caddy:2-alpine caddy hash-password --plaintext "$(p)"

migrate-local: setup ## Миграции Alembic локально (без Docker)
	cd backend && .venv/bin/python -c "from app.migrations import run_migrations; run_migrations()"

# --- Docker: локальная разработка ---

up: setup ## Поднять приложение в Docker (http://127.0.0.1:8000)
	$(COMPOSE_LOCAL) up -d --build

down: ## Остановить локальные контейнеры
	$(COMPOSE_LOCAL) down

restart: ## Перезапустить локальные контейнеры
	$(COMPOSE_LOCAL) restart

rebuild: setup ## Пересобрать локальные контейнеры (НЕ для VPS — используйте prod-rebuild)
	@echo "⚠  На VPS нужен: make prod-rebuild"
	$(COMPOSE_LOCAL) up -d --build --force-recreate

logs: ## Логи локальных контейнеров (follow)
	$(COMPOSE_LOCAL) logs -f

ps: ## Статус локальных контейнеров
	$(COMPOSE_LOCAL) ps

shell: ## Shell в контейнере budget-app (локально)
	$(COMPOSE_LOCAL) exec budget-app bash

db-ui: ## Веб-интерфейс SQLite (http://127.0.0.1:8081)
	@echo "sqlite-web: http://127.0.0.1:8081"

migrate: ## Миграции в Docker (локальный compose)
	$(COMPOSE_LOCAL) exec -T budget-app python -c "from app.migrations import run_migrations; run_migrations()"

migrate-stamp: ## Пометить БД как актуальную (если таблицы уже есть)
	$(COMPOSE_LOCAL) exec -T budget-app alembic stamp head

backup: setup ## Бэкап SQLite в data/backups/
	DATA_DIR=./data ./scripts/backup.sh

# --- Docker: production (Caddy + HTTPS) ---

prod-certs: ## Сгенерировать self-signed сертификат для IP
	@./scripts/gen-certs.sh

prod-up: setup prod-certs ## Поднять prod-стек (Caddy :443 + app)
	$(COMPOSE_PROD) up -d --build

prod-down: ## Остановить prod-стек
	$(COMPOSE_PROD) down

prod-restart: ## Перезапустить prod-стек
	$(COMPOSE_PROD) restart

prod-rebuild: setup ## Пересобрать prod-стек (git pull + build с GIT_COMMIT)
	git fetch origin main && git reset --hard origin/main
	GIT_COMMIT=$$(git rev-parse HEAD) $(COMPOSE_PROD) build budget-app
	GIT_COMMIT=$$(git rev-parse HEAD) $(COMPOSE_PROD) up -d --force-recreate

prod-rebuild-nocache: setup ## Пересобрать prod без Docker cache (если build-arg не помог)
	git fetch origin main && git reset --hard origin/main
	GIT_COMMIT=$$(git rev-parse HEAD) $(COMPOSE_PROD) build --no-cache budget-app
	GIT_COMMIT=$$(git rev-parse HEAD) $(COMPOSE_PROD) up -d --force-recreate

prod-logs: ## Логи prod-стека (follow)
	$(COMPOSE_PROD) logs -f

prod-logs-app: ## Логи только budget-app (без Caddy)
	$(COMPOSE_PROD) logs -f budget-app

prod-tail-ai: ## AI/TG лог-файл на хосте (data volume)
	tail -f data/ai-requests.log

prod-verify: ## Проверить деплой: git, BUILD_ID, app.started в логе
	@echo "==> git: $$(git rev-parse --short HEAD)"
	@echo "==> container BUILD_ID:"
	@$(COMPOSE_PROD) exec -T budget-app cat /app/BUILD_ID
	@if grep -q 'app.started' data/ai-requests.log 2>/dev/null; then \
		echo "OK: app.started в data/ai-requests.log"; \
	else \
		echo "WARN: app.started не найден — подождите старт или проверьте образ"; \
		exit 1; \
	fi

prod-ps: ## Статус prod-контейнеров
	$(COMPOSE_PROD) ps

prod-shell: ## Shell в prod-контейнере budget-app
	$(COMPOSE_PROD) exec budget-app bash

prod-migrate: ## Миграции в prod-стеке
	$(COMPOSE_PROD) exec -T budget-app python -c "from app.migrations import run_migrations; run_migrations()"

prod-migrate-stamp: ## Alembic stamp head в prod-стеке
	$(COMPOSE_PROD) exec -T budget-app alembic stamp head

prod-check: ## Проверить prod: caddy → app
	./scripts/prod-check.sh

prod-caddy-reset: prod-down ## Сбросить кэш Caddy и поднять заново
	-docker volume rm fin-home_caddy_data fin-home_caddy_config 2>/dev/null
	$(MAKE) prod-up

prod-backup: ## Бэкап на сервере (DATA_DIR=./data)
	DATA_DIR=./data ./scripts/backup.sh

# --- VPS / деплой ---

deploy: ## Деплой на VPS (git pull + rebuild, запускать на сервере)
	./scripts/deploy.sh

install-compose: ## Установить docker compose plugin (root на VPS)
	bash scripts/install-compose.sh

vps-setup: ## Первичная настройка VPS (root)
	bash scripts/vps-setup.sh
