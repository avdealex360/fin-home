"""Yandex SpeechKit STT v1 — synchronous recognition of short voice notes.

Telegram voice messages are OGG/Opus, which SpeechKit accepts natively
(format=oggopus), so no transcoding is needed. Sync API limits: 1 MB body,
30 seconds of audio — plenty for a spoken expense note.
"""
from __future__ import annotations

import httpx

_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
_TIMEOUT = 30.0


class SttError(Exception):
    pass


def recognize_ogg(api_key: str, folder_id: str, audio: bytes, lang: str = "ru-RU") -> str:
    params = {"folderId": folder_id, "lang": lang, "format": "oggopus"}
    headers = {"Authorization": f"Api-Key {api_key}"}
    try:
        resp = httpx.post(_URL, params=params, headers=headers, content=audio, timeout=_TIMEOUT)
    except httpx.HTTPError as e:
        raise SttError(f"transport: {e}") from e
    if resp.status_code != 200:
        raise SttError(f"http {resp.status_code}: {resp.text[:300]}")
    return (resp.json().get("result") or "").strip()
