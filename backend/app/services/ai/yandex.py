from __future__ import annotations

import httpx

from app.services.ai.base import AiError

_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
_TIMEOUT = 15.0


class YandexProvider:
    name = "yandex"

    def __init__(self, api_key: str, folder_id: str):
        self.api_key = api_key
        self.folder_id = folder_id

    def _client_factory(self) -> httpx.Client:
        return httpx.Client(timeout=_TIMEOUT)

    def complete(self, system: str, user: str, temperature: float = 0.3) -> str:
        payload = {
            "modelUri": f"gpt://{self.folder_id}/yandexgpt-lite",
            "completionOptions": {"temperature": temperature, "maxTokens": 2000},
            "messages": [
                {"role": "system", "text": system},
                {"role": "user", "text": user},
            ],
        }
        headers = {"Authorization": f"Api-Key {self.api_key}"}
        try:
            with self._client_factory() as client:
                resp = client.post(_URL, json=payload, headers=headers)
        except httpx.HTTPError as e:
            raise AiError(f"yandex transport: {e}") from e
        if resp.status_code != 200:
            raise AiError(f"yandex http {resp.status_code}: {resp.text[:200]}")
        try:
            return resp.json()["result"]["alternatives"][0]["message"]["text"]
        except (KeyError, IndexError, ValueError) as e:
            raise AiError(f"yandex bad response: {e}") from e

    def healthcheck(self) -> bool:
        try:
            self.complete("Ответь одним словом.", "ок")
            return True
        except AiError:
            return False
