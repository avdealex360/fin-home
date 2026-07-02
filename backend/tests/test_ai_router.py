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


def test_parse_entries_yandex_array_and_group_suffix():
    raw = """```
[
    {
        "entries": [
            {
                "amount": 1840,
                "type": "expense",
                "category": "Квартира и жилье (needs)",
                "person": "Общее",
                "date": "2026-07-02",
                "comment": "Ремонт бойлера",
                "confidence": "high"
            }
        ]
    }
]
```"""
    out = parse_entries(raw)
    assert len(out) == 1
    assert out[0].category == "Квартира и жилье"


def test_parse_entries_empty_raises():
    with pytest.raises(AiError):
        parse_entries("no json here")
    with pytest.raises(AiError):
        parse_entries('{"entries":[]}')


def test_prompt_has_category_and_person_rules():
    ctx = ParseContext(
        categories=[{"id": 1, "name": "Продукты", "group": "needs"}],
        users=["Леша", "Катя", "Общий"],
        sender_name="Леша",
        today=date(2026, 7, 2),
        currency="RUB",
    )
    system, _ = build_parse_messages("корм коту 500", ctx)
    assert "ВСЕГДА" in system or "ЗАПРЕЩЕНО" in system
    assert "Общий" in system
    assert "Продукты" in system and "2026-07-02" in system


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


import httpx
from app.services.ai.yandex import YandexProvider


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def test_yandex_complete_success(monkeypatch):
    def handler(request):
        assert "Api-Key testkey" == request.headers["Authorization"]
        body = {"result": {"alternatives": [{"message": {"text": "hello"}}]}}
        return httpx.Response(200, json=body)

    p = YandexProvider("testkey", "folder1")
    monkeypatch.setattr(p, "_client_factory", lambda: httpx.Client(transport=_mock_transport(handler)))
    assert p.complete("sys", "usr") == "hello"


def test_yandex_complete_quota_raises(monkeypatch):
    def handler(request):
        return httpx.Response(429, json={"error": "quota"})

    p = YandexProvider("testkey", "folder1")
    monkeypatch.setattr(p, "_client_factory", lambda: httpx.Client(transport=_mock_transport(handler)))
    with pytest.raises(AiError):
        p.complete("sys", "usr")


from app.services.ai.gigachat import GigaChatProvider


def test_gigachat_oauth_then_complete(monkeypatch):
    calls = {"oauth": 0}

    def handler(request):
        if request.url.path.endswith("/oauth"):
            calls["oauth"] += 1
            assert request.headers["Authorization"] == "Basic authkey"
            return httpx.Response(200, json={"access_token": "tok", "expires_at": 9999999999000})
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(200, json={"choices": [{"message": {"content": "answer"}}]})

    p = GigaChatProvider("authkey")
    monkeypatch.setattr(p, "_client_factory", lambda: httpx.Client(transport=_mock_transport(handler)))
    assert p.complete("sys", "usr") == "answer"
    p.complete("sys", "usr")  # token cached — no second oauth call
    assert calls["oauth"] == 1


def test_gigachat_quota_raises(monkeypatch):
    def handler(request):
        if request.url.path.endswith("/oauth"):
            return httpx.Response(200, json={"access_token": "tok", "expires_at": 9999999999000})
        return httpx.Response(429, json={})

    p = GigaChatProvider("authkey")
    monkeypatch.setattr(p, "_client_factory", lambda: httpx.Client(transport=_mock_transport(handler)))
    with pytest.raises(AiError):
        p.complete("sys", "usr")


def test_gigachat_healthcheck_uses_oauth_only(monkeypatch):
    def handler(request):
        if request.url.path.endswith("/oauth"):
            return httpx.Response(200, json={"access_token": "tok", "expires_at": 9999999999000})
        pytest.fail("healthcheck must not call the chat completion endpoint")

    p = GigaChatProvider("authkey")
    monkeypatch.setattr(p, "_client_factory", lambda: httpx.Client(transport=_mock_transport(handler)))
    assert p.healthcheck() is True


def test_gigachat_healthcheck_false_on_oauth_failure(monkeypatch):
    def handler(request):
        return httpx.Response(401, json={"error": "bad key"})

    p = GigaChatProvider("authkey")
    monkeypatch.setattr(p, "_client_factory", lambda: httpx.Client(transport=_mock_transport(handler)))
    assert p.healthcheck() is False


from app.services.ai import router as ai_router


class _FakeProvider:
    def __init__(self, name, output=None, fail=False):
        self.name = name
        self._output = output
        self._fail = fail

    def complete(self, system, user):
        if self._fail:
            raise AiError("boom")
        return self._output

    def healthcheck(self):
        return not self._fail


def _ctx():
    return ParseContext(categories=[{"id": 1, "name": "Кофе", "group": "wants"}],
                        users=["Леша"], sender_name="Леша", today=date(2026, 7, 2), currency="RUB")


def test_parse_with_fallback_logs_request_and_response(tmp_path, monkeypatch):
    from app.services import ai_trace
    log_path = tmp_path / "ai-requests.log"
    monkeypatch.setattr(ai_trace, "LOG_FILE", log_path)
    good = '{"entries":[{"amount":360,"type":"expense","category":"Кофе","person":null,"date":null,"comment":null,"confidence":"high"}]}'
    providers = [_FakeProvider("yandex", output=good)]
    monkeypatch.setattr(ai_router, "build_providers", lambda db: providers)
    ai_router.parse_with_fallback(None, "кофе 360", _ctx())
    text = log_path.read_text(encoding="utf-8")
    assert "ai.request" in text and "кофе 360" in text
    assert "ai.response" in text and good in text
    assert "ai.parsed" in text


def test_parse_with_fallback_switches_on_failure(monkeypatch):
    good = '{"entries":[{"amount":360,"type":"expense","category":"Кофе","person":null,"date":null,"comment":null,"confidence":"high"}]}'
    providers = [_FakeProvider("yandex", fail=True), _FakeProvider("gigachat", output=good)]
    monkeypatch.setattr(ai_router, "build_providers", lambda db: providers)
    out, provider = ai_router.parse_with_fallback(None, "кофе 360", _ctx())
    assert len(out) == 1 and out[0].amount == Decimal("360")
    assert provider == "gigachat"


def test_parse_with_fallback_all_fail_returns_empty(monkeypatch):
    providers = [_FakeProvider("yandex", fail=True), _FakeProvider("gigachat", fail=True)]
    monkeypatch.setattr(ai_router, "build_providers", lambda db: providers)
    entries, provider = ai_router.parse_with_fallback(None, "кофе 360", _ctx())
    assert entries == [] and provider is None


def test_complete_with_fallback(monkeypatch):
    providers = [_FakeProvider("yandex", fail=True), _FakeProvider("gigachat", output="tip")]
    monkeypatch.setattr(ai_router, "build_providers", lambda db: providers)
    text, provider = ai_router.complete_with_fallback(None, "s", "u")
    assert text == "tip" and provider == "gigachat"


def test_provider_label():
    assert ai_router.provider_label("yandex") == "YandexGPT"
    assert ai_router.provider_label("gigachat") == "GigaChat"
    assert ai_router.provider_label(None) == ""
