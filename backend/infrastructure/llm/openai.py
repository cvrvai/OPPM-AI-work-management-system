"""OpenAI LLM adapter."""

import json
import httpx
from infrastructure.llm.base import LLMAdapter, LLMResponse
from config import get_settings


class OpenAIAdapter(LLMAdapter):
    provider = "openai"

    async def _request(self, model_id: str, prompt: str, json_mode: bool = False) -> dict:
        settings = get_settings()
        body: dict = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

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
