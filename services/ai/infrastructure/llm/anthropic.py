"""Anthropic (Claude) LLM adapter."""

import json
import logging
import httpx
from infrastructure.llm.base import LLMAdapter, LLMResponse, ProviderUnavailableError
from config import get_settings

logger = logging.getLogger(__name__)


class AnthropicAdapter(LLMAdapter):
    provider = "anthropic"

    async def _request(self, model_id: str, prompt: str) -> dict:
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": model_id,
                        "max_tokens": 1024,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                resp.raise_for_status()
                return resp.json()
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise ProviderUnavailableError(self.provider, str(e)) from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (502, 503, 529):
                raise ProviderUnavailableError(self.provider, f"HTTP {e.response.status_code}") from e
            raise

    async def call(self, model_id: str, prompt: str, **kwargs) -> LLMResponse:
        data = await self._request(model_id, prompt)
        text = data["content"][0]["text"]
        return LLMResponse(
            text=text,
            model=model_id,
            provider=self.provider,
            usage=data.get("usage", {}),
        )

    async def call_json(self, model_id: str, prompt: str, **kwargs) -> dict | None:
        data = await self._request(model_id, prompt)
        text = data["content"][0]["text"]
        # Extract JSON from response (Claude may wrap in markdown)
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return None
