from __future__ import annotations

import logging

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


def complete_with_fallback(db: Session, system: str, user: str) -> str | None:
    for provider in build_providers(db):
        try:
            return provider.complete(system, user)
        except AiError as e:
            log.warning("provider %s failed: %s", provider.name, e)
    return None


def parse_with_fallback(db: Session, text: str, ctx: ParseContext) -> list[ParsedEntry]:
    system, user = build_parse_messages(text, ctx)
    for provider in build_providers(db):
        try:
            raw = provider.complete(system, user)
            return parse_entries(raw)
        except AiError as e:
            log.warning("provider %s parse failed: %s", provider.name, e)
    return []
