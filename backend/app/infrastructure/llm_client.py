"""LLM 전송 계층 — Protocol + 타입 정의 (LLMClient, LLMUsage, LLMResponse, Message, _PRICING)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class Message:
    role: str      # "system" | "user" | "assistant"
    content: str


# 모델 패밀리명 → (input $/1M, output $/1M). 모델 ID를 "-" 분리 후 단어 포함 여부로 매칭.
_PRICING: dict[str, tuple[float, float]] = {
    "opus":    (15.0, 75.0),
    "sonnet":  (3.0,  15.0),
    "haiku":   (0.8,   4.0),
}


@dataclass
class LLMUsage:
    """LLM 호출 1회의 토큰 사용량 + 추정 비용."""

    model: str
    input_tokens: int
    output_tokens: int

    @property
    def cost_usd(self) -> float | None:
        """모델별 요금표 기준 추정치. 알 수 없는 모델이면 None."""
        parts = self.model.lower().split("-")
        for family, (in_rate, out_rate) in _PRICING.items():
            if family in parts:
                return self.input_tokens * in_rate * 1e-6 + self.output_tokens * out_rate * 1e-6
        return None


@dataclass
class LLMResponse:
    """LLMClient.complete() 반환값 — 텍스트 + 사용량."""

    text: str
    usage: LLMUsage | None = None


@runtime_checkable
class LLMClient(Protocol):
    def complete(self, messages: list[Message]) -> LLMResponse: ...
