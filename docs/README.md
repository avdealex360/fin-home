# Документация fin-home

Центральный указатель. Начните с [README.md](../README.md), если нужен быстрый старт.

**Production:** https://194.154.29.93

---

## Карта документов

| Документ | Для кого | Содержание |
|----------|----------|------------|
| [README.md](../README.md) | Все | Быстрый старт, ссылки, краткий обзор |
| [PROJECT.md](PROJECT.md) | Пользователи | Бизнес-процессы, интерфейс, архитектура, данные |
| [DEPLOY.md](DEPLOY.md) | DevOps | VPS, Docker, HTTPS, GitHub Actions, troubleshooting |
| [MAKEFILE.md](MAKEFILE.md) | Разработка | Все команды `make` |

---

## С чего начать

### Я хочу пользоваться приложением

1. Откройте https://194.154.29.93 (логин/пароль из `.env` на сервере).
2. Прочитайте [PROJECT.md §4](PROJECT.md#4-ежемесячный-цикл-бизнес-процесс) — ежемесячный цикл.
3. Заполните **План** → вносите операции на **Дашборде**.

### Я хочу запустить локально

```bash
git clone https://github.com/avdealex360/fin-home.git
cd fin-home
make setup && make up
```

→ http://127.0.0.1:8000

Подробнее: [MAKEFILE.md](MAKEFILE.md)

### Я настраиваю VPS с нуля

1. [DEPLOY.md §1–2](DEPLOY.md#шаг-1-подготовка-vps-один-раз) — `make vps-setup`, `.env`, `make prod-up`
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
- [ ] `.env` с сильным `APP_PASSWORD` (deploy)
- [ ] `make prod-up && make prod-migrate && make prod-check`
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
План → стрелки ← → или ссылка «Открыть следующий месяц».

**Где крупные расходы?**  
Только в **Плане** (плановые расходы). Дашборд — для фактических мелких операций.

**Telegram не работает**  
Webhook требует домен с Let's Encrypt. По IP с self-signed — только ручной `make notify` или локальный бот без webhook.

**Где данные?**  
`/opt/fin-home/data/budget.db` на VPS. Не в git, не в Docker-образе.

**Как сделать бэкап?**  
`make prod-backup`. Файлы в `data/backups/budget_YYYYMMDD.sql`.

---

## Структура `docs/`

```
docs/
├── README.md      ← этот файл (индекс)
├── PROJECT.md     ← приложение и бизнес-процессы
├── DEPLOY.md      ← VPS и CI/CD
└── MAKEFILE.md    ← команды make
```

Исходный план разработки (архив): [plan.md](../plan.md)
