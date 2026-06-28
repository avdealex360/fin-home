.DEFAULT_GOAL := help

SHELL := /bin/bash

APP_DIR ?= $(CURDIR)
COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
COMPOSE_LOCAL := $(COMPOSE) -f docker-compose.yml
COMPOSE_PROD := $(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml
PYTHON ?= python3
UVICORN ?= uvicorn

.PHONY: help setup install dev test \
        up down restart rebuild logs ps shell \
        prod-up prod-down prod-restart prod-rebuild prod-logs prod-ps prod-shell \
        prod-migrate prod-migrate-stamp prod-backup prod-check prod-caddy-reset \
        migrate migrate-local migrate-stamp \
        backup notify deploy install-compose vps-setup

help: ## Показать все команды
	@grep -E '^[a-zA-Z0-9_-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- Инициализация ---

setup: ## Создать .env (если нет) и каталог data/backups
	@test -f .env || cp .env.example .env
	@mkdir -p data/backups
	@echo "OK: .env и data/backups готовы"

install: setup ## Установить Python-зависимости локально
	$(PYTHON) -m pip install -r requirements.txt

# --- Локальная разработка (без Docker) ---

dev: setup ## Запустить uvicorn с hot-reload на :8000
	$(UVICORN) app.main:app --reload --host 127.0.0.1 --port 8000

test: ## Запустить тесты
	$(PYTHON) -m pytest tests/ -v

migrate-local: setup ## Миграции Alembic локально (без Docker)
	$(PYTHON) -c "from app.migrations import run_migrations; run_migrations()"

notify: setup ## Отправить Telegram-уведомления (scripts/notify.py)
	$(PYTHON) scripts/notify.py

# --- Docker: локальная разработка ---

up: setup ## Поднять приложение в Docker (http://127.0.0.1:8000)
	$(COMPOSE_LOCAL) up -d --build

down: ## Остановить локальные контейнеры
	$(COMPOSE_LOCAL) down

restart: ## Перезапустить локальные контейнеры
	$(COMPOSE_LOCAL) restart

rebuild: setup ## Пересобрать и поднять локальные контейнеры
	$(COMPOSE_LOCAL) up -d --build --force-recreate

logs: ## Логи локальных контейнеров (follow)
	$(COMPOSE_LOCAL) logs -f

ps: ## Статус локальных контейнеров
	$(COMPOSE_LOCAL) ps

shell: ## Shell в контейнере budget-app (локально)
	$(COMPOSE_LOCAL) exec budget-app bash

migrate: ## Миграции в Docker (локальный compose)
	$(COMPOSE_LOCAL) exec -T budget-app python -c "from app.migrations import run_migrations; run_migrations()"

migrate-stamp: ## Пометить БД как актуальную (если таблицы уже есть)
	$(COMPOSE_LOCAL) exec -T budget-app alembic stamp head

backup: setup ## Бэкап SQLite в data/backups/
	DATA_DIR=./data ./scripts/backup.sh

# --- Docker: production (Caddy + HTTPS) ---

prod-up: setup ## Поднять prod-стек (Caddy :443 + app)
	$(COMPOSE_PROD) up -d --build

prod-down: ## Остановить prod-стек
	$(COMPOSE_PROD) down

prod-restart: ## Перезапустить prod-стек
	$(COMPOSE_PROD) restart

prod-rebuild: setup ## Пересобрать prod-стек
	$(COMPOSE_PROD) up -d --build --force-recreate

prod-logs: ## Логи prod-стека (follow)
	$(COMPOSE_PROD) logs -f

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

prod-caddy-reset: prod-down ## Сбросить сертификаты Caddy и поднять заново
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
