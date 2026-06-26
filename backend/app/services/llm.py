"""LLM abstraction layer — real providers only (no mocks).

A single `complete_json(prompt, system)` interface with pluggable providers:

  * "openrouter" (default) — OpenAI-compatible chat completions via OpenRouter.
  * "watsonx"             — IBM watsonx via LangChain.

Provider selection is config (LLM_PROVIDER); callers always get a JSON object.
There is no mock fallback: if the provider is misconfigured, calls raise LLMError.
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from ..config import settings


class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of an LLM completion."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError(f"No JSON object found in LLM output: {text[:200]!r}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"Invalid JSON from LLM: {exc}") from exc


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
class _OpenRouterProvider:
    def __init__(self) -> None:
        if not settings.OPENROUTER_API_KEY:
            raise LLMError(
                "OPENROUTER_API_KEY is not set. Add it to backend/.env "
                "(LLM_PROVIDER=openrouter)."
            )
        self._url = settings.OPENROUTER_BASE_URL.rstrip("/") + "/chat/completions"
        self._model = settings.OPENROUTER_MODEL
        self._headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ecocomply.local",
            "X-Title": "EcoComply",
        }

    def complete_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            resp = httpx.post(self._url, headers=self._headers, json=body, timeout=60)
        except httpx.HTTPError as exc:
            raise LLMError(f"OpenRouter request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise LLMError(f"OpenRouter {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Unexpected OpenRouter response: {data}") from exc
        return _extract_json(content)


class _WatsonxProvider:
    def __init__(self) -> None:
        from langchain_ibm import WatsonxLLM  # type: ignore

        if not (settings.WATSONX_API_KEY and settings.WATSONX_PROJECT_ID):
            raise LLMError("WATSONX_API_KEY / WATSONX_PROJECT_ID not configured")
        self._llm = WatsonxLLM(
            model_id=settings.WATSONX_MODEL_ID,
            url=settings.WATSONX_URL,
            apikey=settings.WATSONX_API_KEY,
            project_id=settings.WATSONX_PROJECT_ID,
            params={"decoding_method": "greedy", "max_new_tokens": 1200},
        )

    def complete_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        full = f"{system}\n\n{prompt}\n\nRespond with ONLY a valid JSON object."
        return _extract_json(self._llm.invoke(full))


# --------------------------------------------------------------------------- #
# Public client
# --------------------------------------------------------------------------- #
class LLMClient:
    def __init__(self, provider: str | None = None) -> None:
        self.provider_name = provider or settings.LLM_PROVIDER
        if self.provider_name == "watsonx":
            self._provider = _WatsonxProvider()
        else:
            self._provider = _OpenRouterProvider()

    def complete_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        return self._provider.complete_json(prompt, system)


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    """Return a cached LLM client. Raises LLMError if not configured."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
