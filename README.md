# Семейный бюджет

Веб-приложение для ведения семейного бюджета по методу 50/30/20.

## Стек

- Python 3.12 + FastAPI
- SQLite + SQLAlchemy
- HTMX + Jinja2 + Tailwind CDN
- Docker Compose

## Быстрый старт

```bash
make setup          # .env + data/backups
make up             # Docker, http://127.0.0.1:8000
# или без Docker:
make install && make dev
```

Логин/пароль — из `.env` (`APP_USER`, `APP_PASSWORD`).

Полный список команд: **`make help`** или **[docs/MAKEFILE.md](docs/MAKEFILE.md)**.

## Функции

- **Дашборд**: 50/30/20, долги, цели, советы, баланс вклада, доход в EUR
- **План**: лимиты по категориям, плановые расходы и взносы по долгам
- **Аналитика**: план vs факт, накопительный график, средний расход по категории
- **Вклад**: калькулятор, график прогноза, история снимков
- **Мультивалютность**: поле EUR при вводе дохода, курс EUR/RUB и EUR/USD
- **Telegram**: `/add`, `/income`, `/balance` + cron-уведомления

## Команды (Makefile)

| Задача | Команда |
|--------|---------|
| Локальный Docker | `make up` / `make down` / `make logs` |
| Локальная разработка | `make dev` |
| Тесты | `make test` |
| Миграции | `make migrate` или `make migrate-local` |
| Бэкап | `make backup` |
| Production (VPS) | `make prod-up` / `make prod-logs` |
| Деплой на сервере | `make deploy` |

Подробнее: **[docs/MAKEFILE.md](docs/MAKEFILE.md)**

## Первые шаги

1. Заполните **План** на текущий месяц (ожидаемый доход)
2. Проверьте долги и цели в **Настройках** (предзаполнены при первом запуске)
3. Вносите операции с дашборда

## Деплой на VPS

Автодеплой при `git push origin main`. Инструкция: **[docs/DEPLOY.md](docs/DEPLOY.md)**.

```bash
# на VPS (root, один раз)
make vps-setup

# на VPS (deploy)
make setup && nano .env
make prod-up && make prod-migrate
```

Prod URL: **https://194.154.29.93**

## Telegram-бот (опционально)

1. Создайте бота через @BotFather
2. Добавьте в `.env`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_IDS`
3. Webhook: `https://your-domain/telegram/webhook`
4. Уведомления: `make notify` или cron `0 9 * * * cd /opt/fin-home && make notify`

## Бэкап

```bash
make backup
```

Cron на VPS:

```
0 3 * * * cd /opt/fin-home && make prod-backup >> /var/log/fin-home-backup.log 2>&1
```

## Переезд на другой VPS

```bash
tar -czf budget-backup.tar.gz data/ docker-compose.yml .env
scp budget-backup.tar.gz user@new-vps:~/
# на новом VPS:
tar -xzf budget-backup.tar.gz && make prod-up
```

## Документация

- [docs/MAKEFILE.md](docs/MAKEFILE.md) — все команды `make`
- [docs/DEPLOY.md](docs/DEPLOY.md) — деплой на VPS через GitHub Actions
