"""LLM adapter package – provides a unified generate() interface."""

from app.llm.provider import get_llm, LLMProvider, LLMError, LLMTimeout

__all__ = ["get_llm", "LLMProvider", "LLMError", "LLMTimeout"]
