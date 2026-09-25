"""자유 대화 프롬프트 빌더 — 고정 컨텍스트 + 멀티턴 히스토리."""
from __future__ import annotations

from ..llm.client import Message

_MAX_HISTORY = 20  # 컨텍스트 초과 방지: 오래된 메시지부터 제거

_SYSTEM = (
    "너는 사용자가 제공한 문서를 바탕으로 질문에 답하는 도우미다. "
    "[CONTEXT] 블록의 내용만을 근거로 답변하고, 모르는 것은 모른다고 말한다."
)


def _build_system_content(context_text: str, highlights: list[str] | None) -> str:
    """시스템 메시지 content 조립 — 컨텍스트 + (선택) [READER_FOCUS] 블록."""
    content = f"{_SYSTEM}\n\n[CONTEXT]\n{context_text}"
    if highlights:
        focus = "\n".join(f"- {h}" for h in highlights)
        content += f"\n\n[READER_FOCUS]\n독자가 중요하게 표시한 내용:\n{focus}"
    return content


def build_chat_messages(
    context_text: str,
    history: list[dict],
    highlights: list[str] | None = None,
) -> list[Message]:
    """LLMClient.complete()에 넘길 메시지 목록 생성.

    Args:
        context_text: 추출된 페이지 텍스트 (고정, 항상 포함)
        history: [{"role": "user"|"assistant", "content": str}, ...] 순서대로
        highlights: 독자 형광 표시 텍스트 목록 (있을 때만 [READER_FOCUS] 블록 추가)
    """
    trimmed = history[-_MAX_HISTORY:] if len(history) > _MAX_HISTORY else history
    messages = [Message(role="system", content=_build_system_content(context_text, highlights))]
    for i, msg in enumerate(trimmed):
        content = msg["content"]
        if i == len(trimmed) - 1 and msg["role"] == "user":
            content = f"{content}\n[TASK] chat"
        messages.append(Message(role=msg["role"], content=content))
    return messages
