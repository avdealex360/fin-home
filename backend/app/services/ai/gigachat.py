from __future__ import annotations

import time
import uuid

import httpx

from app.services.ai.base import AiError

_OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
_CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
_TIMEOUT = 15.0


class GigaChatProvider:
    name = "gigachat"

    def __init__(self, auth_key: str):
        self.auth_key = auth_key
        self._token: str | None = None
        self._token_exp: float = 0.0

    def _client_factory(self) -> httpx.Client:
        # GigaChat uses the Russian NUC CA; verify=False keeps setup simple for a
        # personal deployment (documented in the setup guide).
        return httpx.Client(timeout=_TIMEOUT, verify=False)

    def _ensure_token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        headers = {
            "Authorization": f"Basic {self.auth_key}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            with self._client_factory() as client:
                resp = client.post(_OAUTH_URL, headers=headers, data={"scope": "GIGACHAT_API_PERS"})
        except httpx.HTTPError as e:
            raise AiError(f"gigachat oauth transport: {e}") from e
        if resp.status_code != 200:
            raise AiError(f"gigachat oauth http {resp.status_code}")
        data = resp.json()
        self._token = data["access_token"]
        # expires_at is epoch millis; fall back to now+25min.
        self._token_exp = data.get("expires_at", 0) / 1000 or (time.time() + 1500)
        return self._token

    def complete(self, system: str, user: str, temperature: float = 0.3) -> str:
        token = self._ensure_token()
        payload = {
            "model": "GigaChat",
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            with self._client_factory() as client:
                resp = client.post(_CHAT_URL, json=payload, headers=headers)
        except httpx.HTTPError as e:
            raise AiError(f"gigachat transport: {e}") from e
        if resp.status_code != 200:
            raise AiError(f"gigachat http {resp.status_code}: {resp.text[:200]}")
        try:
            return resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            raise AiError(f"gigachat bad response: {e}") from e

    def healthcheck(self) -> bool:
        try:
            self._ensure_token()
            return True
        except AiError:
            return False
