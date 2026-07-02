from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol


class AiError(Exception):
    """Provider failed (quota, transport, HTTP, or unparseable output)."""


@dataclass
class ParsedEntry:
    amount: Decimal
    type: str  # "expense" | "income"
    category: str | None
    person: str | None
    date: date | None
    comment: str | None
    confidence: str  # "high" | "low"


@dataclass
class ParseContext:
    categories: list[dict]  # {"id", "name", "group"}
    users: list[str]
    sender_name: str
    today: date
    currency: str


class AiProvider(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str: ...

    def healthcheck(self) -> bool: ...


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def build_parse_messages(text: str, ctx: ParseContext) -> tuple[str, str]:
    cats = "\n".join(f'- {c["name"]} ({c["group"]})' for c in ctx.categories)
    people = ", ".join(ctx.users)
    system = (
        "Ты — парсер бытовых финансовых заметок семьи. Извлеки из текста список операций.\n"
        f"Сегодня: {ctx.today.isoformat()}. Валюта: {ctx.currency}.\n"
        f"Отправитель сообщения: {ctx.sender_name}.\n"
        f"Люди: {people}.\n"
        "Доступные категории (выбирай ТОЛЬКО из этого списка):\n"
        f"{cats}\n\n"
        "Верни СТРОГО JSON без пояснений в формате:\n"
        '{"entries":[{"amount":число,"type":"expense|income","category":"имя из списка или null",'
        '"person":"имя человека, или null","date":"YYYY-MM-DD или null","comment":"строка или null",'
        '"confidence":"high|low"}]}\n'
        "Правила:\n"
        "- amount — число без пробелов и валюты.\n"
        "- category: ВСЕГДА выбирай одну наиболее близкую по смыслу категорию из списка "
        "(ремонт / газ / коммуналка / быт → бытовая нужда; еда вне дома / доставка → рестораны; "
        "сигареты / алкоголь / развлечения → развлечения; корм / ветеринар / питомец → категория питомца). "
        "Ставь category=null ТОЛЬКО если ни одна категория даже отдалённо не подходит; "
        "не сваливай всё в «Прочее» / «Буфер».\n"
        "- person: если в тексте назван человек — этот человек; "
        "если трата общая или бытовая (аренда, ремонт, коммуналка, интернет, продукты, питомец, уборка) — «Общее»; "
        "если это личное потребление (кофе, сигареты, личная одежда) — отправитель; иначе — отправитель.\n"
        "- Относительные даты («вчера», «позавчера», «N дней назад», «в понедельник») "
        "вычисляй в YYYY-MM-DD от сегодняшней даты; если дата не упомянута — null.\n"
        "- Зарплата / поступление → type=income, иначе expense.\n"
        "- confidence=low, если категория или человек выбраны по догадке.\n"
        "Примеры:\n"
        "«ремонт газа в квартире 1840» → category = ближайшая бытовая категория, person=«Общее».\n"
        "«корм коту 500» → category = категория питомца, person=«Общее».\n"
        "«сигареты 3500» → category = развлечения / личное, person=отправитель, confidence=low."
    )
    return system, text


def _to_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _to_decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def parse_entries(raw: str) -> list[ParsedEntry]:
    match = _JSON_RE.search(raw or "")
    if not match:
        raise AiError("no JSON object in model output")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise AiError(f"invalid JSON: {e}") from e

    entries: list[ParsedEntry] = []
    for item in data.get("entries", []):
        amount = _to_decimal(item.get("amount"))
        if amount is None or amount <= 0:
            continue
        entries.append(
            ParsedEntry(
                amount=amount,
                type="income" if item.get("type") == "income" else "expense",
                category=item.get("category") or None,
                person=item.get("person") or None,
                date=_to_date(item.get("date")),
                comment=item.get("comment") or None,
                confidence="low" if item.get("confidence") == "low" else "high",
            )
        )
    if not entries:
        raise AiError("no usable entries")
    return entries
