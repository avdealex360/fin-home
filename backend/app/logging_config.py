from __future__ import annotations

import logging
import sys
from pathlib import Path

# Uvicorn and Alembic both reconfigure logging on startup — wire handlers in
# lifespan *after* run_migrations(), and mirror to a file on the data volume.
_APP_LOGGERS = ("ai.router", "telegram_bot", "tg_client", "app.tg_webhook")
LOG_FILE = Path("./data/ai-debug.log")


class _FlushingHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


def configure_app_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    stream = _FlushingHandler(sys.stderr)
    stream.setFormatter(fmt)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(fmt)
    for name in _APP_LOGGERS:
        lg = logging.getLogger(name)
        lg.setLevel(logging.INFO)
        lg.handlers.clear()
        lg.addHandler(stream)
        lg.addHandler(file_handler)
        lg.propagate = False
    logging.getLogger("ai.router").info("logging ready, file=%s", LOG_FILE.resolve())
