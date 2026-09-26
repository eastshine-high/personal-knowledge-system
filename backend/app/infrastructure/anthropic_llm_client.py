"""AnthropicLLMClient — 실 Anthropic Claude API 클라이언트."""
from __future__ import annotations

from .llm_client import LLMResponse, LLMUsage, Message


class AnthropicLLMClient:
    """실 Anthropic Claude 클라이언트.

    ANTHROPIC_API_KEY 환경변수에서 키를 읽는다.
    system 역할 메시지는 Anthropic API의 최상위 system 파라미터로 분리해 전달한다.
    """

    def __init__(self, model: str = "claude-sonnet-4-6", max_tokens: int = 4096) -> None:
        try:
            import anthropic as _anthropic
        except ImportError as exc:
            raise ImportError("pip install anthropic") from exc
        self._client = _anthropic.Anthropic()  # ANTHROPIC_API_KEY 환경변수 자동 사용
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, messages: list[Message]) -> LLMResponse:
        system_text = "\n\n".join(m.content for m in messages if m.role == "system")
        chat = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]

        kwargs: dict = dict(model=self._model, max_tokens=self._max_tokens, messages=chat)
        if system_text:
            kwargs["system"] = system_text

        resp = self._client.messages.create(**kwargs)
        if not resp.content:
            raise RuntimeError(f"Anthropic 응답 content가 비어 있습니다 (model={self._model})")
        usage = LLMUsage(
            model=self._model,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
        )
        return LLMResponse(text=resp.content[0].text, usage=usage)
