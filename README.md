# Семейный бюджет

Веб-приложение для ведения семейного бюджета по методу 50/30/20.

## Стек

- Python 3.12 + FastAPI
- SQLite + SQLAlchemy
- HTMX + Jinja2 + Tailwind CDN
- Docker Compose

## Функции

- **Дашборд**: 50/30/20, долги, цели, советы, баланс вклада, доход в EUR
- **План**: лимиты по категориям, плановые расходы и взносы по долгам
- **Аналитика**: план vs факт, накопительный график, средний расход по категории
- **Вклад**: калькулятор, график прогноза, история снимков
- **Мультивалютность**: поле EUR при вводе дохода, курс EUR/RUB и EUR/USD
- **Telegram**: `/add`, `/income`, `/balance` + cron-уведомления (`scripts/notify.py`)

## Быстрый старт

```bash
cp .env.example .env
# Отредактируйте APP_USER и APP_PASSWORD

mkdir -p data/backups
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Или через Docker:

```bash
cp .env.example .env
docker compose up -d --build
```

Откройте http://127.0.0.1:8000 — браузер запросит логин/пароль из `.env`.

## Первые шаги

1. Заполните **План** на текущий месяц (ожидаемый доход)
2. Проверьте долги и цели в **Настройках** (предзаполнены при первом запуске)
3. Начните вносить операции с дашборда или страницы «Операция»

## Бэкап

```bash
chmod +x scripts/backup.sh
./scripts/backup.sh
```

Cron (ежедневно в 3:00):

```
0 3 * * * DATA_DIR=/path/to/fin-home/data /path/to/fin-home/scripts/backup.sh
```

## Telegram-бот (опционально)

1. Создайте бота через @BotFather
2. Добавьте в `.env`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_IDS` (ваш user id)
3. Установите webhook: `https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-domain/telegram/webhook`
4. Уведомления: `0 9 * * * python /path/to/scripts/notify.py`

## Деплой на VPS

Автодеплой через GitHub Actions при push в `main`. Подробная инструкция: **[docs/DEPLOY.md](docs/DEPLOY.md)**.

Кратко:

1. На VPS: `bash scripts/vps-setup.sh` (от root)
2. Создать `.env` на сервере, первый запуск через `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
3. Добавить GitHub Secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`
4. `git push origin main` — деплой автоматически

Prod URL: **https://194.154.29.93** (самоподписанный сертификат до появления домена).

## Переезд на другой VPS

```bash
tar -czf budget-backup.tar.gz data/ docker-compose.yml .env
scp budget-backup.tar.gz user@new-vps:~/
# на новом VPS:
tar -xzf budget-backup.tar.gz && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```
