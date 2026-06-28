# Деплой fin-home на VPS

Автодеплой при push в `main` через GitHub Actions. На сервере: Docker Compose + Caddy (HTTPS).

**VPS:** `194.154.29.93` (Ubuntu 24.04)  
**Репозиторий:** https://github.com/avdealex360/fin-home

## Архитектура

```
git push main → GitHub Actions → SSH → scripts/deploy.sh
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

Скопируйте и запустите скрипт (после первого push с деплоем в репозиторий):

```bash
git clone https://github.com/avdealex360/fin-home.git /opt/fin-home
bash /opt/fin-home/scripts/vps-setup.sh
```

Или до push — с локальной машины:

```bash
scp scripts/vps-setup.sh root@194.154.29.93:/tmp/
ssh root@194.154.29.93 'bash /tmp/vps-setup.sh'
```

Скрипт установит Docker, создаст пользователя `deploy`, настроит UFW (22, 80, 443) и клонирует репозиторий в `/opt/fin-home`.

### Ограничить доступ только через VPN (опционально)

Если Amnezia VPN использует подсеть, например `10.8.0.0/24`:

```bash
VPN_CIDR=10.8.0.0/24 bash /opt/fin-home/scripts/vps-setup.sh
```

---

## Шаг 2. Секреты приложения на VPS

```bash
ssh deploy@194.154.29.93
cd /opt/fin-home
cp .env.example .env
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
mkdir -p data/backups
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T budget-app alembic upgrade head
```

Откройте в браузере: **https://194.154.29.93**

Браузер покажет предупреждение о самоподписанном сертификате — это нормально без домена. Нажмите «Продолжить» / «Advanced → Proceed».

---

## Шаг 3. SSH-ключ для GitHub Actions

На **локальной машине**:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/fin-home-deploy -N ""
cat ~/.ssh/fin-home-deploy.pub
```

Публичный ключ добавьте на VPS:

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

Репозиторий → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret | Значение |
|--------|----------|
| `VPS_HOST` | `194.154.29.93` |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | содержимое файла `~/.ssh/fin-home-deploy` (приватный ключ целиком) |

Опционально:

| Secret | Значение |
|--------|----------|
| `VPS_APP_PATH` | `/opt/fin-home` (по умолчанию) |

---

## Шаг 5. Автодеплой

Каждый push в `main` запускает workflow **Deploy**:

```bash
git push origin main
```

Проверка: GitHub → **Actions** → последний run должен быть зелёным.

На VPS:

```bash
ssh deploy@194.154.29.93
cd /opt/fin-home
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50
```

Ручной деплой без push:

```bash
ssh deploy@194.154.29.93 'cd /opt/fin-home && ./scripts/deploy.sh'
```

Или в GitHub: **Actions** → **Deploy** → **Run workflow**.

---

## Шаг 6. Бэкап базы

Ежедневный cron на VPS (от root или deploy):

```bash
crontab -e
```

```
0 3 * * * DATA_DIR=/opt/fin-home/data /opt/fin-home/scripts/backup.sh >> /var/log/fin-home-backup.log 2>&1
```

Восстановление из дампа:

```bash
sqlite3 /opt/fin-home/data/budget.db < /opt/fin-home/data/backups/budget_YYYYMMDD.sql
```

---

## Когда появится домен

1. Направьте A-запись домена на `194.154.29.93`.
2. В [`Caddyfile`](../Caddyfile) замените IP на домен и уберите `tls internal`:

```
budget.example.com {
    reverse_proxy budget-app:8000
}
```

3. Перезапустите: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d caddy`

Caddy автоматически получит сертификат Let's Encrypt.

---

## Устранение неполадок

**Workflow падает на SSH**

- Проверьте секреты `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`.
- Убедитесь, что ключ `deploy` в `authorized_keys`.

**502 Bad Gateway**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs budget-app
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs caddy
```

**`.env not found` при деплое**

Файл `.env` не в git — создайте его на VPS вручную (шаг 2).

**Миграции**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec budget-app alembic upgrade head
```

**Локальная разработка без Caddy**

```bash
docker compose up -d --build
# http://127.0.0.1:8000
```
