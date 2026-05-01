"""DeepSeek LLM adapter (OpenAI-compatible API)."""

import json
import logging
import httpx
from infrastructure.llm.base import LLMAdapter, LLMResponse, ProviderUnavailableError
from config import get_settings

logger = logging.getLogger(__name__)


class DeepSeekAdapter(LLMAdapter):
    provider = "deepseek"

    async def _request(self, model_id: str, prompt: str, json_mode: bool = False) -> dict:
        settings = get_settings()
        body: dict = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        base_url = settings.deepseek_base_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                    json=body,
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
        text = data["choices"][0]["message"]["content"]
        return LLMResponse(
            text=text,
            model=model_id,
            provider=self.provider,
            usage=data.get("usage", {}),
        )

    async def call_json(self, model_id: str, prompt: str, **kwargs) -> dict | None:
        data = await self._request(model_id, prompt, json_mode=True)
        text = data["choices"][0]["message"]["content"]
        return json.loads(text)
