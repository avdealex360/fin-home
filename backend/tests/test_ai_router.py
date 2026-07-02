from datetime import date
from decimal import Decimal
import pytest

from app.services.ai.base import parse_entries, build_parse_messages, ParseContext, AiError


def test_parse_entries_valid_json():
    raw = '{"entries":[{"amount":1560,"type":"expense","category":"Продукты","person":null,"date":null,"comment":"магазин","confidence":"high"}]}'
    out = parse_entries(raw)
    assert len(out) == 1
    assert out[0].amount == Decimal("1560")
    assert out[0].type == "expense"
    assert out[0].category == "Продукты"
    assert out[0].date is None
    assert out[0].confidence == "high"


def test_parse_entries_with_iso_date():
    raw = '{"entries":[{"amount":360,"type":"expense","category":"Кофе","person":"Катя","date":"2026-07-01","comment":null,"confidence":"low"}]}'
    out = parse_entries(raw)
    assert out[0].date == date(2026, 7, 1)
    assert out[0].person == "Катя"


def test_parse_entries_strips_code_fence():
    raw = "```json\n{\"entries\":[{\"amount\":100,\"type\":\"expense\",\"category\":null,\"person\":null,\"date\":null,\"comment\":null,\"confidence\":\"high\"}]}\n```"
    out = parse_entries(raw)
    assert out[0].amount == Decimal("100")


def test_parse_entries_empty_raises():
    with pytest.raises(AiError):
        parse_entries("no json here")
    with pytest.raises(AiError):
        parse_entries('{"entries":[]}')


def test_build_parse_messages_includes_categories_and_today():
    ctx = ParseContext(
        categories=[{"id": 1, "name": "Продукты", "group": "needs"}],
        users=["Леша", "Катя", "Общий"],
        sender_name="Леша",
        today=date(2026, 7, 2),
        currency="RUB",
    )
    system, user = build_parse_messages("кофе 360", ctx)
    assert "Продукты" in system
    assert "2026-07-02" in system
    assert "кофе 360" in user
