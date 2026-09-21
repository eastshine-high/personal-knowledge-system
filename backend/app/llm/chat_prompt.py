"""자유 대화 프롬프트 빌더 — 고정 컨텍스트 + 멀티턴 히스토리."""
from __future__ import annotations

from ..llm.client import Message

_MAX_HISTORY = 20  # 컨텍스트 초과 방지: 오래된 메시지부터 제거

_SYSTEM = (
    "너는 사용자가 제공한 문서를 바탕으로 질문에 답하는 도우미다. "
    "[CONTEXT] 블록의 내용만을 근거로 답변하고, 모르는 것은 모른다고 말한다."
)


def build_chat_messages(context_text: str, history: list[dict]) -> list[Message]:
    """LLMClient.complete()에 넘길 메시지 목록 생성.

    Args:
        context_text: 추출된 페이지 텍스트 (고정, 항상 포함)
        history: [{"role": "user"|"assistant", "content": str}, ...] 순서대로
    """
    trimmed = history[-_MAX_HISTORY:] if len(history) > _MAX_HISTORY else history

    system_content = f"{_SYSTEM}\n\n[CONTEXT]\n{context_text}"
    messages = [Message(role="system", content=system_content)]
    for msg in trimmed:
        messages.append(Message(role=msg["role"], content=msg["content"]))
    return messages
