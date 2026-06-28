# Деплой fin-home на VPS

Автодеплой при push в `main` через GitHub Actions. На сервере: Docker Compose + Caddy (HTTPS).

**VPS:** `194.154.29.93` (Ubuntu 24.04)  
**Репозиторий:** https://github.com/avdealex360/fin-home

Команды ниже можно заменить на **`make`** — полный справочник: [MAKEFILE.md](MAKEFILE.md).

## Архитектура

```
git push main → GitHub Actions → SSH → make deploy
                                              ↓
                                    docker compose (prod)
                                              ↓
                              Caddy :443 → budget-app :8000
```

Данные SQLite хранятся в `/opt/fin-home/data/` на хосте и не теряются при деплое.

---

## Шаг 1. Подготовка VPS (один раз)

Подключитесь к серверу как root:

```bash
ssh root@194.154.29.93
```

```bash
git clone https://github.com/avdealex360/fin-home.git /opt/fin-home
cd /opt/fin-home
make vps-setup
```

Или до push — с локальной машины:

```bash
scp scripts/vps-setup.sh root@194.154.29.93:/tmp/
ssh root@194.154.29.93 'bash /tmp/vps-setup.sh'
```

Скрипт установит Docker, Compose, пользователя `deploy`, UFW (22, 80, 443) и клонирует репозиторий.

### Docker Compose не найден

Часто на VPS с Amnezia Docker есть, а Compose — нет. От root:

```bash
cd /opt/fin-home
make install-compose
docker compose version
```

### Ограничить доступ только через VPN (опционально)

```bash
VPN_CIDR=10.8.0.0/24 make vps-setup
```

---

## Шаг 2. Секреты приложения на VPS

```bash
ssh deploy@194.154.29.93
cd /opt/fin-home
make setup
nano .env
```

Обязательно задайте:

```env
APP_USER=admin
APP_PASSWORD=ваш_длинный_пароль
APP_SECRET=случайная_строка_32_символа
```

Первый запуск:

```bash
make prod-up
make prod-migrate
```

Если миграции падают с `table app_users already exists`:

```bash
make prod-migrate-stamp
```

Откройте: **https://194.154.29.93** (примите предупреждение о самоподписанном сертификате).

---

## Шаг 3. SSH-ключ для GitHub Actions

На **локальной машине**:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/fin-home-deploy -N ""
cat ~/.ssh/fin-home-deploy.pub
```

Публичный ключ на VPS:

```bash
ssh root@194.154.29.93
mkdir -p /home/deploy/.ssh
echo "ВСТАВЬТЕ_ПУБЛИЧНЫЙ_КЛЮЧ" >> /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
```

Проверка:

```bash
ssh -i ~/.ssh/fin-home-deploy deploy@194.154.29.93 'echo OK'
```

---

## Шаг 4. Секреты в GitHub

Repo → **Settings** → **Secrets and variables** → **Actions**:

| Secret | Значение |
|--------|----------|
| `VPS_HOST` | `194.154.29.93` |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | приватный ключ `~/.ssh/fin-home-deploy` целиком |

---

## Шаг 5. Автодеплой

```bash
git push origin main
```

Проверка: GitHub → **Actions** → workflow **Deploy**.

На VPS:

```bash
make prod-ps
make prod-logs
```

Ручной деплой:

```bash
ssh deploy@194.154.29.93 'cd /opt/fin-home && make deploy'
```

Или: GitHub → **Actions** → **Deploy** → **Run workflow**.

---

## Шаг 6. Бэкап базы

```bash
make prod-backup
```

Cron на VPS:

```
0 3 * * * cd /opt/fin-home && make prod-backup >> /var/log/fin-home-backup.log 2>&1
```

Восстановление:

```bash
sqlite3 /opt/fin-home/data/budget.db < /opt/fin-home/data/backups/budget_YYYYMMDD.sql
```

---

## Когда появится домен

1. A-запись домена → `194.154.29.93`
2. В [`Caddyfile`](../Caddyfile) замените IP на домен, уберите `tls internal`
3. `make prod-restart` или `make prod-rebuild`

---

## Устранение неполадок

| Проблема | Решение |
|----------|---------|
| `unknown shorthand flag: 'f'` | `make install-compose` (от root) |
| `table app_users already exists` | `make prod-migrate-stamp` |
| 502 Bad Gateway | `make prod-logs`, `make prod-check` |
| ERR_SSL_PROTOCOL_ERROR | `make prod-caddy-reset`, см. ниже |
| `.env not found` при деплое | `make setup && nano .env` |
| Workflow падает на SSH | Проверить GitHub Secrets и `authorized_keys` |

**ERR_SSL_PROTOCOL_ERROR при открытии https://194.154.29.93**

1. Обновите код и перезапустите Caddy (исправлен `Caddyfile` — порты вместо IP):

```bash
git pull origin main
make prod-rebuild
make prod-check
```

2. Если не помогло — сброс сертификатов Caddy:

```bash
make prod-caddy-reset
make prod-check
```

3. Проверьте, не занят ли 443 другим сервисом (Amnezia VPN):

```bash
sudo ss -tlnp | grep -E ':443|:80'
make prod-logs
```

4. Временный обход — HTTP (если редирект мешает, в `Caddyfile` замените блок `:80` на `reverse_proxy budget-app:8000`):

```bash
curl -I http://194.154.29.93
```

**Логи приложения:**

```bash
make prod-logs
# только budget-app:
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs budget-app
```

**Локальная разработка без Caddy:**

```bash
make up
# http://127.0.0.1:8000
```

---

## Справочник make-команд

| Команда | Где |
|---------|-----|
| `make prod-up` | Поднять prod на VPS |
| `make prod-down` | Остановить |
| `make prod-rebuild` | Пересобрать после git pull |
| `make prod-migrate` | Миграции |
| `make prod-migrate-stamp` | Исправить конфликт Alembic |
| `make prod-backup` | Бэкап SQLite |
| `make deploy` | Полный деплой (git pull + rebuild) |
| `make install-compose` | Установить Compose (root) |
| `make vps-setup` | Первичная настройка VPS (root) |

Полный список: [MAKEFILE.md](MAKEFILE.md)
