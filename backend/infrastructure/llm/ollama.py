"""Ollama (local) LLM adapter."""

import json
import httpx
from infrastructure.llm.base import LLMAdapter, LLMResponse
from config import get_settings


class OllamaAdapter(LLMAdapter):
    provider = "ollama"

    async def call(self, model_id: str, prompt: str, **kwargs) -> LLMResponse:
        settings = get_settings()
        url = kwargs.get("endpoint_url") or settings.ollama_url
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{url}/api/chat",
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("message", {}).get("content", "")
            return LLMResponse(text=text, model=model_id, provider=self.provider)

    async def call_json(self, model_id: str, prompt: str, **kwargs) -> dict | None:
        settings = get_settings()
        url = kwargs.get("endpoint_url") or settings.ollama_url
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{url}/api/chat",
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "format": "json",
                },
            )
            resp.raise_for_status()
            text = resp.json().get("message", {}).get("content", "")
            return json.loads(text)
