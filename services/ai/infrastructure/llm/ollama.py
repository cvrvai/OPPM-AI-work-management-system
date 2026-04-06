"""Ollama (local/cloud) LLM adapter."""

import base64
import json
import logging
import httpx
from infrastructure.llm.base import LLMAdapter, LLMResponse, ProviderUnavailableError
from config import get_settings

logger = logging.getLogger(__name__)


class OllamaAdapter(LLMAdapter):
    provider = "ollama"

    def _url(self, **kwargs) -> str:
        settings = get_settings()
        return kwargs.get("endpoint_url") or settings.ollama_url

    async def health_check(self, **kwargs) -> bool:
        url = self._url(**kwargs)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{url}/api/tags")
                return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def call(self, model_id: str, prompt: str, **kwargs) -> LLMResponse:
        url = self._url(**kwargs)
        try:
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
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise ProviderUnavailableError(self.provider, str(e)) from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 502, 503):
                raise ProviderUnavailableError(self.provider, f"HTTP {e.response.status_code}") from e
            raise

    async def call_json(self, model_id: str, prompt: str, **kwargs) -> dict | None:
        url = self._url(**kwargs)
        try:
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
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise ProviderUnavailableError(self.provider, str(e)) from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 502, 503):
                raise ProviderUnavailableError(self.provider, f"HTTP {e.response.status_code}") from e
            raise

    async def call_vision_json(
        self, model_id: str, prompt: str, image_bytes: bytes, **kwargs
    ) -> dict | None:
        """Send an image + prompt to an Ollama vision model and return parsed JSON.

        The model must support multimodal input (e.g. llava, llama3.2-vision,
        bakllava).  ``image_bytes`` is the raw binary image data (PNG/JPEG/WEBP).
        """
        url = self._url(**kwargs)
        image_b64 = base64.b64encode(image_bytes).decode()
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    f"{url}/api/chat",
                    json={
                        "model": model_id,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt,
                                "images": [image_b64],
                            }
                        ],
                        "stream": False,
                        "format": "json",
                    },
                )
                resp.raise_for_status()
                text = resp.json().get("message", {}).get("content", "")
                return json.loads(text)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise ProviderUnavailableError(self.provider, str(e)) from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 502, 503):
                raise ProviderUnavailableError(self.provider, f"HTTP {e.response.status_code}") from e
            raise
        except json.JSONDecodeError as e:
            logger.warning("Ollama vision returned non-JSON: %s", e)
            return None
