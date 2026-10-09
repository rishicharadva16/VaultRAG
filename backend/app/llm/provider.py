"""
LLM provider interface and implementations.

All LLM calls go through the generate() method of an LLMProvider.
The LLM is NEVER loaded in-process; it is called over HTTP.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Non-retryable LLM error (bad config, missing model, etc.)."""


class LLMTimeout(Exception):
    """LLM request timed out or Ollama is unreachable."""


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    def generate(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        temperature: float = 0,
        json_mode: bool = False,
    ) -> str:
        """Send messages to the LLM and return the assistant response text."""
        ...

    def health(self) -> dict:
        """Return {"status": "ok"} or {"status": "unavailable", "detail": ...}."""
        return {"status": "ok"}


class OllamaProvider(LLMProvider):
    """Ollama HTTP API provider (default)."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        fallback_model: str | None = None,
        timeout: int | None = None,
    ):
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model = model or settings.LLM_MODEL
        self._fallback_model = fallback_model or settings.LLM_FALLBACK_MODEL
        self._timeout = timeout or settings.LLM_TIMEOUT_S

    def generate(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        temperature: float = 0,
        json_mode: bool = False,
    ) -> str:
        return self._call(
            self._model, messages, max_tokens, temperature, json_mode, allow_fallback=True
        )

    def _call(
        self,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int | None,
        temperature: float,
        json_mode: bool,
        allow_fallback: bool,
    ) -> str:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "seed": 42,
                "num_ctx": 4096,
                "num_predict": max_tokens or settings.LLM_MAX_TOKENS,
            },
            "keep_alive": "30m",
        }
        if json_mode:
            body["format"] = "json"

        try:
            resp = httpx.post(
                f"{self._base_url}/api/chat",
                json=body,
                timeout=self._timeout,
            )
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            if allow_fallback and self._fallback_model and self._fallback_model != model:
                logger.warning(
                    "Ollama primary model %s unreachable, falling back to %s",
                    model, self._fallback_model,
                )
                return self._call(
                    self._fallback_model, messages, max_tokens, temperature,
                    json_mode, allow_fallback=False,
                )
            raise LLMTimeout(f"Ollama unreachable: {exc}") from exc

        if resp.status_code != 200:
            error_detail = resp.text[:200]
            if allow_fallback and self._fallback_model and self._fallback_model != model:
                logger.warning(
                    "Ollama model %s failed (HTTP %d), falling back to %s",
                    model, resp.status_code, self._fallback_model,
                )
                return self._call(
                    self._fallback_model, messages, max_tokens, temperature,
                    json_mode, allow_fallback=False,
                )
            raise LLMError(f"Ollama returned {resp.status_code}: {error_detail}")

        data = resp.json()
        content = data.get("message", {}).get("content", "")
        return content

    def health(self) -> dict:
        try:
            resp = httpx.get(f"{self._base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                return {"status": "ok", "models": models}
            return {"status": "unavailable", "detail": f"HTTP {resp.status_code}"}
        except Exception as exc:
            return {"status": "unavailable", "detail": str(exc)}


class FakeLLM(LLMProvider):
    """Deterministic LLM for tests. Returns whatever response is scripted."""

    def __init__(self):
        self._responses: list[str] = []
        self._calls: list[dict] = []
        self._should_timeout: bool = False

    def set_responses(self, *responses: str) -> None:
        """Set a queue of responses; they are consumed in order."""
        self._responses = list(responses)

    def set_timeout(self, should_timeout: bool = True) -> None:
        self._should_timeout = should_timeout

    def generate(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        temperature: float = 0,
        json_mode: bool = False,
    ) -> str:
        self._calls.append({
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "json_mode": json_mode,
        })
        if self._should_timeout:
            raise LLMTimeout("FakeLLM simulated timeout")
        if not self._responses:
            raise LLMError("FakeLLM has no responses queued")
        return self._responses.pop(0)

    @property
    def call_count(self) -> int:
        return len(self._calls)

    @property
    def last_call(self) -> dict | None:
        return self._calls[-1] if self._calls else None


# ── Hosted stubs (disabled by default) ──────────────────────


class HostedProviderStub(LLMProvider):
    """Stub for hosted providers (Groq, Gemini). Raises if not configured."""

    def __init__(self, name: str):
        self._name = name

    def generate(self, messages, max_tokens=None, temperature=0, json_mode=False) -> str:
        raise LLMError(
            f"{self._name} provider is not configured. "
            f"Set LLM_FALLBACK_ENABLED=true and the appropriate API key."
        )

    def health(self) -> dict:
        return {"status": "unavailable", "detail": f"{self._name} not configured"}


# ── Factory ──────────────────────────────────────────────────


_provider_instance: LLMProvider | None = None


def get_llm() -> LLMProvider:
    """Return the singleton LLM provider based on settings."""
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    provider_name = settings.LLM_PROVIDER.lower()
    if provider_name == "ollama":
        _provider_instance = OllamaProvider()
    elif provider_name == "groq":
        _provider_instance = HostedProviderStub("Groq")
    elif provider_name == "gemini":
        _provider_instance = HostedProviderStub("Gemini")
    else:
        _provider_instance = OllamaProvider()

    return _provider_instance


def set_llm(provider: LLMProvider) -> None:
    """Override the LLM provider (for tests)."""
    global _provider_instance
    _provider_instance = provider


def reset_llm() -> None:
    """Reset the LLM provider singleton (for tests)."""
    global _provider_instance
    _provider_instance = None
