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


_GROUP_SUFFIX_RE = re.compile(
    r"\s*\((?:needs|wants|savings|income|нужды|желания|накопления)\)\s*$",
    re.IGNORECASE,
)


def _normalize_category_name(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = _GROUP_SUFFIX_RE.sub("", name.strip())
    return cleaned or None


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def build_parse_messages(text: str, ctx: ParseContext) -> tuple[str, str]:
    cats = "\n".join(f'- "{c["name"]}" (группа: {c["group"]})' for c in ctx.categories)
    people = ", ".join(ctx.users)
    system = (
        "Ты — парсер бытовых финансовых заметок семьи. Извлеки из текста список операций.\n"
        f"Сегодня: {ctx.today.isoformat()}. Валюта: {ctx.currency}.\n"
        f"Отправитель сообщения: {ctx.sender_name}.\n"
        f"Люди: {people}.\n"
        "Доступные категории — в поле category пиши ТОЧНОЕ имя в кавычках (без группы в скобках):\n"
        f"{cats}\n\n"
        "Верни СТРОГО JSON без пояснений в формате:\n"
        '{"entries":[{"amount":число,"type":"expense|income","category":"имя из списка или null",'
        '"person":"имя человека, или null","date":"YYYY-MM-DD или null","comment":"строка или null",'
        '"confidence":"high|low"}]}\n'
        "Правила:\n"
        "- amount — число без пробелов и валюты.\n"
        "- category: строка = ТОЧНОЕ имя категории из списка (например «Квартира и жилье», «Связь и интернет»). "
        "ЗАПРЕЩЕНО писать needs/wants/savings/income или «группа» — только русское имя категории. "
        "Несколько трат в одном сообщении → несколько entries, у каждой своя category.\n"
        "- comment: короткая фраза из исходного текста для этой операции (например «Ремонт бойлера», «Табачки для кальяна»).\n"
        "- person: имя из списка людей; общие/бытовые траты → «Общий» (если есть в списке), иначе отправитель; "
        "личное потребление → отправитель.\n"
        "- Относительные даты («вчера», «позавчера») → YYYY-MM-DD от сегодня; иначе null.\n"
        "- Зарплата / поступление → type=income, иначе expense.\n"
        "- confidence=low, если категория или человек выбраны по догадке.\n"
        "Примеры (category = точное имя):\n"
        "«ремонт бойлера 1840» → category=«Квартира и жилье», comment=«ремонт бойлера», person=«Общий».\n"
        "«табак для кальяна 3037» → category=«Рестораны и доставка» или «Подписки и развлечения», person=отправитель.\n"
        "«яндекс облако 500» → category=«Связь и интернет», comment=«яндекс облако», person=«Общий»."
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
    text = raw or ""
    match = _JSON_RE.search(text)
    if not match:
        raise AiError("no JSON object in model output")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise AiError(f"invalid JSON: {e}") from e

    if isinstance(data, list):
        if not data or not isinstance(data[0], dict):
            raise AiError("no usable entries")
        data = data[0]

    entries: list[ParsedEntry] = []
    for item in data.get("entries", []):
        amount = _to_decimal(item.get("amount"))
        if amount is None or amount <= 0:
            continue
        entries.append(
            ParsedEntry(
                amount=amount,
                type="income" if item.get("type") == "income" else "expense",
                category=_normalize_category_name(item.get("category")),
                person=item.get("person") or None,
                date=_to_date(item.get("date")),
                comment=item.get("comment") or None,
                confidence="low" if item.get("confidence") == "low" else "high",
            )
        )
    if not entries:
        raise AiError("no usable entries")
    return entries
