from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path(os.environ.get("AI_TRACE_FILE", "./data/ai-requests.log"))


def trace_block(title: str, **sections: str) -> None:
    """Append a human-readable block to the trace file (flush + fsync)."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [f"=== {ts} {title} ==="]
    for name, body in sections.items():
        lines.append(f"--- {name} ---")
        lines.append(body)
    lines.append("")
    text = "\n".join(lines)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
