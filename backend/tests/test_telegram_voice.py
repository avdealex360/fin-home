"""Voice-message flow: TG voice → SpeechKit STT → parsed expense."""
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import AppUser, Category, Transaction
from app.services import telegram_bot, tg_client
from app.services.ai import speechkit
from app.services.ai.base import ParsedEntry
from app.services.ai.speechkit import SttError
from app.services.tg_client import TgError
from tests.conftest import WS, create_workspace


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    create_workspace(session)
    yield session
    session.close()


def _seed(db):
    db.add_all([
        Category(workspace_id=WS, name="Кофе", group="wants", sort_order=1),
        AppUser(workspace_id=WS, name="Леша", telegram_id="111"),
    ])
    db.commit()


def _secrets(values):
    def fake(db, key, default=""):
        return values.get(key, default)
    return fake


_ALL_KEYS = {
    "secret.tg_bot_token": "tok",
    "secret.yandex_api_key": "ykey",
    "secret.yandex_folder_id": "yfolder",
}


def _voice_update(duration=5, file_id="f1"):
    return {"message": {
        "voice": {"file_id": file_id, "duration": duration, "mime_type": "audio/ogg"},
        "chat": {"id": 111}, "from": {"id": 111},
    }}


def test_voice_transcribed_and_written(db, monkeypatch):
    _seed(db)
    monkeypatch.setattr(telegram_bot, "get_secret", _secrets(_ALL_KEYS))
    monkeypatch.setattr(telegram_bot, "download_file", lambda token, file_id: b"OGGDATA")
    monkeypatch.setattr(
        telegram_bot, "recognize_ogg",
        lambda key, folder, audio, lang="ru-RU": "кофе 360")
    monkeypatch.setattr(
        telegram_bot, "parse_with_fallback",
        lambda d, text, ctx: (
            [ParsedEntry(Decimal("360"), "expense", "Кофе", None, None, "кофе", "high")],
            "yandex",
        ),
    )
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message",
                        lambda token, chat_id, text, reply_markup=None: sent.append(text))

    telegram_bot.handle_update(db, _voice_update())

    assert db.query(Transaction).count() == 1
    assert any("Услышал" in t and "кофе 360" in t for t in sent)


def test_voice_too_long_rejected_without_download(db, monkeypatch):
    _seed(db)
    monkeypatch.setattr(telegram_bot, "get_secret", _secrets(_ALL_KEYS))

    def no_download(token, file_id):
        raise AssertionError("must not download long voice")
    monkeypatch.setattr(telegram_bot, "download_file", no_download)
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message",
                        lambda token, chat_id, text, reply_markup=None: sent.append(text))

    telegram_bot.handle_update(db, _voice_update(duration=45))

    assert db.query(Transaction).count() == 0
    assert sent and "30 секунд" in sent[0]


def test_voice_exactly_30s_rejected(db, monkeypatch):
    # duration is rounded by TG; a 30.4s file arrives as 30 and the sync API
    # would reject it — the bot must cut at 29.
    _seed(db)
    monkeypatch.setattr(telegram_bot, "get_secret", _secrets(_ALL_KEYS))
    monkeypatch.setattr(telegram_bot, "download_file",
                        lambda *a: (_ for _ in ()).throw(AssertionError("no download")))
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message",
                        lambda token, chat_id, text, reply_markup=None: sent.append(text))

    telegram_bot.handle_update(db, _voice_update(duration=30))

    assert db.query(Transaction).count() == 0
    assert sent and "30 секунд" in sent[0]


def test_voice_without_stt_keys_prompts_setup(db, monkeypatch):
    _seed(db)
    monkeypatch.setattr(telegram_bot, "get_secret",
                        _secrets({"secret.tg_bot_token": "tok"}))
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message",
                        lambda token, chat_id, text, reply_markup=None: sent.append(text))

    telegram_bot.handle_update(db, _voice_update())

    assert db.query(Transaction).count() == 0
    assert sent and "не настроено" in sent[0].lower()


def test_voice_stt_error_reports_friendly(db, monkeypatch):
    _seed(db)
    monkeypatch.setattr(telegram_bot, "get_secret", _secrets(_ALL_KEYS))
    monkeypatch.setattr(telegram_bot, "download_file", lambda token, file_id: b"OGGDATA")

    def boom(*a, **k):
        raise SttError("http 429: quota")
    monkeypatch.setattr(telegram_bot, "recognize_ogg", boom)
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message",
                        lambda token, chat_id, text, reply_markup=None: sent.append(text))

    telegram_bot.handle_update(db, _voice_update())

    assert db.query(Transaction).count() == 0
    assert sent and "распознать" in sent[0].lower()


def test_voice_empty_transcript_reports(db, monkeypatch):
    _seed(db)
    monkeypatch.setattr(telegram_bot, "get_secret", _secrets(_ALL_KEYS))
    monkeypatch.setattr(telegram_bot, "download_file", lambda token, file_id: b"OGGDATA")
    monkeypatch.setattr(telegram_bot, "recognize_ogg", lambda *a, **k: "")
    sent = []
    monkeypatch.setattr(telegram_bot, "send_message",
                        lambda token, chat_id, text, reply_markup=None: sent.append(text))

    telegram_bot.handle_update(db, _voice_update())

    assert db.query(Transaction).count() == 0
    assert sent  # some "could not hear" reply, no crash


# --- speechkit unit ---------------------------------------------------------

def test_recognize_ogg_sends_key_and_params(monkeypatch):
    seen = {}

    def fake_post(url, params=None, headers=None, content=None, timeout=None):
        seen.update(url=url, params=params, headers=headers, content=content)
        return httpx.Response(200, json={"result": "кофе триста шестьдесят"},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(speechkit.httpx, "post", fake_post)

    out = speechkit.recognize_ogg("k1", "fold1", b"OGG")

    assert out == "кофе триста шестьдесят"
    assert seen["params"]["folderId"] == "fold1"
    assert seen["params"]["format"] == "oggopus"
    assert seen["headers"]["Authorization"] == "Api-Key k1"
    assert seen["content"] == b"OGG"


def test_recognize_ogg_http_error_raises(monkeypatch):
    def fake_post(url, **kw):
        return httpx.Response(403, text="forbidden", request=httpx.Request("POST", url))
    monkeypatch.setattr(speechkit.httpx, "post", fake_post)
    with pytest.raises(SttError):
        speechkit.recognize_ogg("k", "f", b"OGG")


# --- tg_client.download_file ------------------------------------------------

def test_download_file_two_step(monkeypatch):
    def handler(request):
        if request.url.path.endswith("/getFile"):
            return httpx.Response(200, json={"ok": True, "result": {"file_path": "voice/1.oga"}})
        assert request.url.path == "/file/bottok/voice/1.oga"
        return httpx.Response(200, content=b"OGGBYTES")

    monkeypatch.setattr(tg_client, "_client_factory",
                        lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    assert tg_client.download_file("tok", "f1") == b"OGGBYTES"


def test_download_file_missing_path_raises(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"ok": True, "result": {}})
    monkeypatch.setattr(tg_client, "_client_factory",
                        lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(TgError):
        tg_client.download_file("tok", "f1")
