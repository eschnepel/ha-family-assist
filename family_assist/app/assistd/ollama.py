from __future__ import annotations

import json
from typing import AsyncIterator

import httpx


class OllamaError(Exception):
    pass


class OllamaClient:
    def __init__(self, base_url: str, api_key: str = "", *, timeout: float = 600.0,
                 transport: httpx.AsyncBaseTransport | None = None):
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(timeout, connect=10.0),
            transport=transport,
        )

    async def chat_stream(self, *, model: str, messages: list[dict], tools: list[dict],
                          num_ctx: int) -> AsyncIterator[dict]:
        payload: dict = {"model": model, "messages": messages, "stream": True, "options": {"num_ctx": num_ctx}}
        if tools:
            payload["tools"] = tools
        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", errors="replace")[:300]
                    raise OllamaError(f"Ollama returned {response.status_code}: {body}")
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except ValueError:
                        raise OllamaError("Invalid response from Ollama") from None
                    if chunk.get("error"):
                        raise OllamaError(str(chunk["error"])[:300])
                    yield chunk
        except httpx.HTTPError as exc:
            raise OllamaError(f"Cannot reach Ollama ({type(exc).__name__})") from None

    async def check_model(self, model: str) -> dict:
        """Reachability and capabilities of a model; never raises."""
        result: dict = {"model": model, "reachable": False, "exists": False, "tools": None, "vision": None}
        try:
            response = await self._client.post("/api/show", json={"model": model}, timeout=8.0)
        except httpx.HTTPError:
            return result
        result["reachable"] = True
        if response.status_code == 404:
            return result
        if response.status_code != 200:
            result["error"] = f"HTTP {response.status_code}"
            return result
        result["exists"] = True
        capabilities = response.json().get("capabilities")
        if isinstance(capabilities, list):
            result["tools"] = "tools" in capabilities
            result["vision"] = "vision" in capabilities
        return result

    async def aclose(self) -> None:
        await self._client.aclose()
