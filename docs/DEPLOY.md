# Деплой fin-home на VPS

Автодеплой при push в `main` через GitHub Actions. На сервере: Docker Compose + Caddy (HTTPS).

**VPS:** `194.154.29.93` (Ubuntu 24.04)  
**Репозиторий:** https://github.com/avdealex360/fin-home  
**URL:** https://194.154.29.93

Связанные документы: [PROJECT.md](PROJECT.md) · [MAKEFILE.md](MAKEFILE.md) · [README.md](../README.md)

---

## Архитектура

```
git push main → GitHub Actions → SSH → make deploy
                                              ↓
                         docker compose (prod): Caddy + budget-app
                                              ↓
                              Caddy :443 → budget-app :8000
                                              ↓
                              ./data/budget.db (на диске VPS)
```

TLS: self-signed сертификат для IP (`scripts/gen-certs.sh` → `certs/`).  
`tls internal` в Caddy **не использовать** — ломает handshake на IP.

---

## Шаг 1. Подготовка VPS (один раз)

```bash
ssh root@194.154.29.93
git clone https://github.com/avdealex360/fin-home.git /opt/fin-home
cd /opt/fin-home
make vps-setup
```

Скрипт: Docker, Compose, пользователь `deploy`, UFW (22, 80, 443), клон репозитория.

### Docker Compose не найден

На VPS с Amnezia часто нет `docker compose`. От root:

```bash
cd /opt/fin-home
make install-compose
docker compose version
```

### Доступ только через VPN (опционально)

```bash
VPN_CIDR=10.8.0.0/24 make vps-setup
```

---

## Шаг 2. Секреты и первый запуск

```bash
ssh deploy@194.154.29.93
cd /opt/fin-home
make setup
nano .env
```

```env
APP_USER=admin
APP_PASSWORD=ваш_длинный_пароль
APP_SECRET=случайная_строка_32_символа
```

```bash
make prod-up          # gen-certs + Caddy + app
make prod-migrate
make prod-check       # все проверки OK
```

Откройте **https://194.154.29.93** → примите предупреждение о сертификате → логин из `.env`.

Если миграции: `table app_users already exists` → `make prod-migrate-stamp`

---

## Шаг 3. SSH-ключ для GitHub Actions

На локальной машине:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/fin-home-deploy -N ""
cat ~/.ssh/fin-home-deploy.pub
```

На VPS (root):

```bash
mkdir -p /home/deploy/.ssh
echo "ПУБЛИЧНЫЙ_КЛЮЧ" >> /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys
```

Проверка: `ssh -i ~/.ssh/fin-home-deploy deploy@194.154.29.93 'echo OK'`

---

## Шаг 4. Секреты GitHub

**Без этих секретов Actions падает с `missing server host`.**

Откройте: https://github.com/avdealex360/fin-home/settings/secrets/actions → **New repository secret**

| Secret | Значение |
|--------|----------|
| `VPS_HOST` | `194.154.29.93` |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | содержимое **приватного** ключа (весь файл, включая `-----BEGIN OPENSSH PRIVATE KEY-----`) |

Как получить ключ (если ещё не создавали):

```bash
ssh-keygen -t ed25519 -f ~/.ssh/fin-home-deploy -N ""
cat ~/.ssh/fin-home-deploy      # → VPS_SSH_KEY
cat ~/.ssh/fin-home-deploy.pub  # → authorized_keys на VPS
```

Публичный ключ на VPS:

```bash
ssh root@194.154.29.93
mkdir -p /home/deploy/.ssh
echo "СОДЕРЖИМОЕ .pub" >> /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys
```

Проверка:

```bash
ssh -i ~/.ssh/fin-home-deploy deploy@194.154.29.93 'echo OK'
```

После добавления секретов: **Actions → Deploy → Run workflow** или `git push origin main`.

---

## Шаг 5. Автодеплой

```bash
git push origin main
```

Проверка: GitHub → Actions → **Deploy**.

На VPS:

```bash
make prod-ps
make prod-logs
make prod-check
```

Ручной деплой: `ssh deploy@194.154.29.93 'cd /opt/fin-home && make deploy'`

---

## Шаг 6. Бэкап

```bash
make prod-backup
```

Cron:

```
0 3 * * * cd /opt/fin-home && make prod-backup >> /var/log/fin-home-backup.log 2>&1
```

Восстановление:

```bash
sqlite3 /opt/fin-home/data/budget.db < /opt/fin-home/data/backups/budget_YYYYMMDD.sql
```

---

## HTTPS и сертификаты

| Файл | Назначение |
|------|------------|
| `scripts/gen-certs.sh` | Генерация self-signed для IP |
| `certs/cert.pem`, `certs/key.pem` | Сертификат (не в git) |
| `Caddyfile` | `:443` + `tls /certs/...` |

Пересоздать сертификат:

```bash
rm -rf certs/
make prod-certs
make prod-rebuild
```

Проверка:

```bash
curl -Ik https://194.154.29.93 --insecure   # ожидается HTTP/2 401
make prod-check
```

---

## Когда появится домен

1. A-запись → `194.154.29.93`
2. В `Caddyfile` заменить блок на:

```
your-domain.com {
    reverse_proxy budget-app:8000
}
```

3. Убрать volume `./certs` из `docker-compose.prod.yml` (Caddy получит Let's Encrypt сам)
4. `make prod-rebuild`

Telegram webhook заработает с валидным HTTPS-доменом.

---

## Устранение неполадок

| Проблема | Решение |
|----------|---------|
| `unknown shorthand flag: 'f'` | `make install-compose` (root) |
| `table app_users already exists` | `make prod-migrate-stamp` |
| 502 Bad Gateway | `make prod-logs`, `make prod-check` |
| ERR_SSL_PROTOCOL_ERROR | `rm -rf certs && make prod-certs && make prod-rebuild` |
| `make rebuild` на VPS | **Не использовать** — только `make prod-rebuild` |
| `.env not found` | `make setup && nano .env` |
| SSH deploy падает | GitHub Secrets, `authorized_keys` |
| prod-check FAIL на :443 | `make prod-caddy-reset`, проверить `certs/` |

Логи:

```bash
make prod-logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs budget-app
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs caddy
```

---

## Справочник make-команд (prod)

| Команда | Описание |
|---------|----------|
| `make prod-up` | Сертификат + Caddy + app |
| `make prod-down` | Остановить |
| `make prod-rebuild` | Пересобрать после git pull |
| `make prod-migrate` | Миграции Alembic |
| `make prod-migrate-stamp` | Исправить конфликт миграций |
| `make prod-check` | Диагностика HTTPS |
| `make prod-certs` | Только сертификат |
| `make prod-caddy-reset` | Сброс кэша Caddy |
| `make prod-backup` | Бэкап SQLite |
| `make deploy` | git pull + rebuild + migrate |

Полный список: [MAKEFILE.md](MAKEFILE.md)
