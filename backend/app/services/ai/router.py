from __future__ import annotations

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
from app.services.ai_trace import trace_block
from app.services.settings_store import get_secret, get_setting


def _log_request(kind: str, provider: str, attempt: int, total: int, system: str, user: str) -> None:
    trace_block(
        f"ai.request kind={kind} provider={provider} attempt={attempt}/{total}",
        system=system,
        user=user,
    )


def _log_response(kind: str, provider: str, elapsed_ms: float, raw: str, *, extra: str = "") -> None:
    title = f"ai.response kind={kind} provider={provider} elapsed_ms={elapsed_ms:.0f}"
    if extra:
        title += f" {extra}"
    trace_block(title, raw=raw)


def _log_failure(kind: str, provider: str, elapsed_ms: float | None, error: str, raw: str | None = None) -> None:
    ms = f"{elapsed_ms:.0f}" if elapsed_ms is not None else "?"
    sections: dict[str, str] = {"error": error}
    if raw is not None:
        sections["raw"] = raw
    trace_block(f"ai.failed kind={kind} provider={provider} elapsed_ms={ms}", **sections)


def _complete_logged(
    provider: AiProvider, kind: str, attempt: int, total: int, system: str, user: str, temperature: float = 0.3
) -> str:
    _log_request(kind, provider.name, attempt, total, system, user)
    t0 = time.monotonic()
    try:
        raw = provider.complete(system, user, temperature)
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


def complete_with_fallback(
    db: Session, system: str, user: str, temperature: float = 0.3
) -> tuple[str | None, str | None]:
    providers = build_providers(db)
    total = len(providers)
    for attempt, provider in enumerate(providers, 1):
        try:
            raw = _complete_logged(provider, "complete", attempt, total, system, user, temperature)
            return raw, provider.name
        except AiError:
            continue
    trace_block(f"ai.exhausted kind=complete providers={total}")
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
        trace_block(f"ai.parsed kind=parse provider={provider.name} entries={len(entries)}")
        return entries, provider.name
    trace_block(f"ai.exhausted kind=parse providers={total}", user_text=text)
    return [], None
