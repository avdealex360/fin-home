#!/bin/bash
set -euo pipefail

DATA_DIR="${DATA_DIR:-/app/data}"
BACKUP_DIR="${DATA_DIR}/backups"
DB_FILE="${DATA_DIR}/budget.db"

mkdir -p "$BACKUP_DIR"

if [ -f "$DB_FILE" ]; then
    sqlite3 "$DB_FILE" ".dump" > "${BACKUP_DIR}/budget_$(date +%Y%m%d).sql"
    find "$BACKUP_DIR" -name "budget_*.sql" -mtime +30 -delete
    echo "Backup created: budget_$(date +%Y%m%d).sql"
else
    echo "Database not found: $DB_FILE"
    exit 1
fi
