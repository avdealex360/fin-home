from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.services.ai.base import (
    AiError,
    AiProvider,
    ParseContext,
    ParsedEntry,
    build_parse_messages,
    parse_entries,
)
from app.services.ai.gigachat import GigaChatProvider
from app.services.ai.yandex import YandexProvider
from app.services.settings_store import get_secret, get_setting

log = logging.getLogger("ai.router")
def _log_request(kind: str, provider: str, attempt: int, total: int, system: str, user: str) -> None:
    log.info(
        "ai.request kind=%s provider=%s attempt=%d/%d\n"
        "--- system ---\n%s\n"
        "--- user ---\n%s",
        kind, provider, attempt, total, system, user,
    )


def _log_response(kind: str, provider: str, elapsed_ms: float, raw: str, *, extra: str = "") -> None:
    suffix = f" {extra}" if extra else ""
    log.info(
        "ai.response kind=%s provider=%s elapsed_ms=%.0f%s\n"
        "--- raw ---\n%s",
        kind, provider, elapsed_ms, suffix, raw,
    )


def _log_failure(kind: str, provider: str, elapsed_ms: float | None, error: str, raw: str | None = None) -> None:
    if raw is not None:
        log.warning(
            "ai.failed kind=%s provider=%s elapsed_ms=%s error=%s\n"
            "--- raw ---\n%s",
            kind, provider,
            f"{elapsed_ms:.0f}" if elapsed_ms is not None else "?",
            error, raw,
        )
    else:
        log.warning(
            "ai.failed kind=%s provider=%s elapsed_ms=%s error=%s",
            kind, provider,
            f"{elapsed_ms:.0f}" if elapsed_ms is not None else "?",
            error,
        )


def _complete_logged(provider: AiProvider, kind: str, attempt: int, total: int, system: str, user: str) -> str:
    _log_request(kind, provider.name, attempt, total, system, user)
    t0 = time.monotonic()
    try:
        raw = provider.complete(system, user)
    except AiError as e:
        elapsed_ms = (time.monotonic() - t0) * 1000
        _log_failure(kind, provider.name, elapsed_ms, str(e))
        raise
    elapsed_ms = (time.monotonic() - t0) * 1000
    _log_response(kind, provider.name, elapsed_ms, raw)
    return raw


def build_providers(db: Session) -> list[AiProvider]:
    yandex_key = get_secret(db, "secret.yandex_api_key")
    yandex_folder = get_secret(db, "secret.yandex_folder_id")
    giga_key = get_secret(db, "secret.gigachat_auth_key")

    available: dict[str, AiProvider] = {}
    if yandex_key and yandex_folder:
        available["yandex"] = YandexProvider(yandex_key, yandex_folder)
    if giga_key:
        available["gigachat"] = GigaChatProvider(giga_key)

    primary = get_setting(db, "ai_primary_provider", "yandex")
    order = [primary] + [n for n in ("yandex", "gigachat") if n != primary]
    return [available[n] for n in order if n in available]


_PROVIDER_LABELS = {"yandex": "YandexGPT", "gigachat": "GigaChat"}


def provider_label(name: str | None) -> str:
    return _PROVIDER_LABELS.get(name or "", name or "")


def complete_with_fallback(db: Session, system: str, user: str) -> tuple[str | None, str | None]:
    providers = build_providers(db)
    total = len(providers)
    for attempt, provider in enumerate(providers, 1):
        try:
            raw = _complete_logged(provider, "complete", attempt, total, system, user)
            return raw, provider.name
        except AiError:
            continue
    log.warning("ai.exhausted kind=complete providers=%d", total)
    return None, None


def parse_with_fallback(
    db: Session, text: str, ctx: ParseContext
) -> tuple[list[ParsedEntry], str | None]:
    system, user = build_parse_messages(text, ctx)
    providers = build_providers(db)
    total = len(providers)
    for attempt, provider in enumerate(providers, 1):
        try:
            raw = _complete_logged(provider, "parse", attempt, total, system, user)
        except AiError:
            continue
        try:
            entries = parse_entries(raw)
        except AiError as e:
            _log_failure("parse", provider.name, None, f"parse_entries: {e}", raw=raw)
            continue
        log.info("ai.parsed kind=parse provider=%s entries=%d", provider.name, len(entries))
        return entries, provider.name
    log.warning("ai.exhausted kind=parse providers=%d user_text=%s", total, text)
    return [], None
