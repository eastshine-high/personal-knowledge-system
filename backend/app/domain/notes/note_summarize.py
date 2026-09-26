"""요약/리파인 프롬프트 빌더 — 범용 LLMClient 위에서 노트 로직을 수행.

LLMClient는 "그냥 LLM"(complete). 여기서 **어떻게 프롬프트할지**(요약/리파인)와 출력 파싱(NoteDraft)을 담당한다.
공급자를 바꿔도(mock/anthropic/openai/local) 이 로직은 그대로다.

메시지 규약(user): `[LABEL] value` 단일 라인 + `[TEXT]`/`[NOTE]`/`[SOURCE]` 멀티라인 블록.
LLM 출력 규약: 첫 줄 `TITLE: <제목>`, 빈 줄, 그다음 마크다운 본문.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ...llm import LLMClient, Message
from .note_models import NoteDraft

_SYSTEM = (
    "너는 스캔 문서에서 추출한 텍스트로 개념 요약 노트를 만드는 도우미다. "
    "출력은 반드시 첫 줄에 'TITLE: <제목>', 빈 줄, 그다음 마크다운 본문 형식으로 낸다. "
    "주어진 텍스트 외의 사실을 지어내지 않는다."
)


@dataclass
class SummarizeRequest:
    """요약 요청 파라미터 — 텍스트 + 주제/가이드라인/highlights."""

    text: str
    topic: str
    guideline: str | None = None
    note_count: int = 1
    highlights: list[str] | None = None


@dataclass
class RefineRequest:
    """리파인 요청 파라미터 — 현재 노트 + 지시 + 원문 + 이력 + 가이드라인."""

    note_markdown: str
    instruction: str
    text: str
    history: list[str] | None = None
    guideline: str | None = None


def _build_summarize_prompt(req: SummarizeRequest, aspect: str) -> str:
    """요약 프롬프트 조립 — highlights 있을 때만 [READER_FOCUS] 블록 포함."""
    lines = [
        "[TASK] summarize",
        f"[TOPIC] {req.topic}",
        f"[GUIDELINE] {req.guideline or ''}",
        f"[ASPECT] {aspect}",
        "[TEXT]",
        req.text,
    ]
    if req.highlights:
        lines += [
            "",
            "[READER_FOCUS]",
            "다음은 독자가 이 페이지에서 중요하다고 표시한 구절입니다.",
            "요약은 이 독자의 이해 방식을 반영해야 합니다:",
        ]
        lines += [f"- {h}" for h in req.highlights]
    return "\n".join(lines)


def summarize(client: LLMClient, req: SummarizeRequest) -> list[NoteDraft]:
    """추출 텍스트를 topic/guideline에 맞춰 note_count개 노트 초안으로 요약."""
    drafts: list[NoteDraft] = []
    for i in range(1, req.note_count + 1):
        prompt = _build_summarize_prompt(req, f"{i}/{req.note_count}")
        out = client.complete([Message("system", _SYSTEM), Message("user", prompt)])
        drafts.append(_parse_draft(out.text))
    return drafts


def refine(client: LLMClient, req: RefineRequest) -> NoteDraft:
    """현재 노트를 후속 지시로 다듬는다. 원문 텍스트 + 최근 지시(history)를 맥락으로 전달(다중턴)."""
    lines = ["[TASK] refine"]
    if req.guideline:
        lines.append(f"[GUIDELINE] {req.guideline}")
    if req.history:
        lines.append("[HISTORY]")
        lines += [f"- {h}" for h in req.history]
    lines += [
        f"[INSTRUCTION] {req.instruction}",
        "[NOTE]",
        req.note_markdown,
        "[SOURCE]",
        req.text,
    ]
    out = client.complete([Message("system", _SYSTEM), Message("user", "\n".join(lines))])
    return _parse_draft(out.text)


def _parse_draft(text: str) -> NoteDraft:
    """LLM 출력('TITLE: ...' + 본문)을 NoteDraft로 파싱. 형식 이탈 시 관대하게 처리."""
    text = text.strip()
    lines = text.splitlines()
    if lines and lines[0].strip().upper().startswith("TITLE:"):
        title = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).strip()
    else:
        title = (lines[0].strip() if lines else "")[:60]
        body = text
    return NoteDraft(title=title or "무제", body=body)
