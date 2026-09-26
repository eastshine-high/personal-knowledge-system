"""LLM 전송 계층 — 범용 LLMClient + 설정 기반 공급자 스왑."""
from __future__ import annotations

from ..config import Settings, get_settings
from .client import AnthropicLLMClient, LLMClient, LLMResponse, LLMUsage, Message, MockLLMClient

__all__ = ["AnthropicLLMClient", "LLMClient", "LLMResponse", "LLMUsage", "Message", "MockLLMClient", "get_llm_client"]


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    """LLM_BACKEND 설정에 따라 LLMClient 구현을 반환한다."""
    s = settings or get_settings()
    if s.llm_backend == "mock":
        return MockLLMClient()
    if s.llm_backend == "anthropic":
        return AnthropicLLMClient(model=s.llm_model)
    if s.llm_backend in ("openai", "local"):
        raise NotImplementedError(f"{s.llm_backend} LLM 어댑터는 미구현")
    raise ValueError(f"unknown LLM_BACKEND: {s.llm_backend}")
