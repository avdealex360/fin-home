from __future__ import annotations

import logging
import sys

# Uvicorn reconfigures logging on startup and drops handlers attached at import
# time — wire these loggers in lifespan instead.
_APP_LOGGERS = ("ai.router", "telegram_bot", "tg_client")


def configure_app_logging() -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    for name in _APP_LOGGERS:
        lg = logging.getLogger(name)
        lg.setLevel(logging.INFO)
        lg.handlers.clear()
        lg.addHandler(handler)
        lg.propagate = False
