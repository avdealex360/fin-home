from __future__ import annotations

import logging

import httpx

_API = "https://api.telegram.org"
_TIMEOUT = 15.0
log = logging.getLogger("tg_client")


class TgError(Exception):
    pass


def _client_factory() -> httpx.Client:
    return httpx.Client(timeout=_TIMEOUT)


def _call(token: str, method: str, payload: dict) -> dict:
    url = f"{_API}/bot{token}/{method}"
    try:
        with _client_factory() as client:
            resp = client.post(url, json=payload)
    except httpx.HTTPError as e:
        raise TgError(f"transport: {e}") from e
    data = resp.json()
    if not data.get("ok"):
        raise TgError(f"{method} failed: {data.get('description')}")
    return data.get("result", {})


def send_message(token: str, chat_id: int | str, text: str, reply_markup: dict | None = None) -> None:
    # Best-effort: log and swallow so a reply failure never breaks the webhook.
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        _call(token, "sendMessage", payload)
    except TgError as e:
        log.warning("sendMessage failed: %s", e)


def answer_callback_query(token: str, callback_query_id: str, text: str = "") -> None:
    try:
        _call(token, "answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})
    except TgError as e:
        log.warning("answerCallbackQuery failed: %s", e)


def get_me(token: str) -> dict:
    return _call(token, "getMe", {})


def set_webhook(token: str, url: str, secret_token: str) -> dict:
    return _call(token, "setWebhook", {"url": url, "secret_token": secret_token})
