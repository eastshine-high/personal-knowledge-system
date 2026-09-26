"""MockLLMClient — 결정적 오프라인 LLM 구현."""
from __future__ import annotations

import re

from .llm_client import LLMResponse, LLMUsage, Message


def _field(text: str, label: str) -> str:
    """`[LABEL] value` 형태의 단일 라인 값 추출."""
    m = re.search(rf"^\[{label}\][ \t]*(.*)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _block(text: str, label: str) -> str:
    """`[LABEL]` 라인 다음부터 다음 `[LABEL]` 라인 전까지의 멀티라인 블록."""
    lines = text.splitlines()
    out: list[str] = []
    collecting = False
    for line in lines:
        if re.match(r"^\[[A-Z]+\]", line):
            if collecting:
                break
            collecting = line.startswith(f"[{label}]")
            continue
        if collecting:
            out.append(line)
    return "\n".join(out).strip()


class MockLLMClient:
    """결정적 mock — notes 프롬프트 빌더의 라벨을 읽어 재현 가능한 응답을 만든다.

    실제 요약 품질이 아니라 **파이프라인을 오프라인·결정적으로** 돌리기 위한 것.
    guideline/instruction을 출력에 반영해 테스트로 검증 가능하게 한다.
    """

    def complete(self, messages: list[Message]) -> LLMResponse:
        user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        task = _field(user, "TASK")
        if task == "refine":
            instruction = _field(user, "INSTRUCTION")
            note = _block(user, "NOTE")
            title = _current_title(note) or "리파인된 노트"
            body = _current_body(note) or note
            text = f"TITLE: {title}\n\n{body}\n\n[리파인 반영: {instruction}]"
        elif task == "chat":
            text = f"[Mock 응답] {user[:80].strip()}"
        else:
            text = _mock_summarize(user)
        return LLMResponse(text=text, usage=LLMUsage(model="mock", input_tokens=0, output_tokens=0))


def _mock_summarize(user: str) -> str:
    """[TASK] summarize 분기 — topic/guideline/aspect/text 필드로 결정적 초안 생성."""
    topic = _field(user, "TOPIC") or "요약"
    guideline = _field(user, "GUIDELINE")
    aspect = _field(user, "ASPECT")
    excerpt = _block(user, "TEXT")[:200].strip()
    title = topic if aspect in ("", "1/1") else f"{topic} ({aspect})"
    lines = [f"TITLE: {title}", "", f"## {topic}", "", excerpt]
    if guideline:
        lines += ["", f"[가이드라인 반영: {guideline}]"]
    return "\n".join(lines)


def _current_title(note_markdown: str) -> str:
    for line in note_markdown.splitlines():
        if line.strip().upper().startswith("TITLE:"):
            return line.split(":", 1)[1].strip()
    return ""


def _current_body(note_markdown: str) -> str:
    lines = note_markdown.splitlines()
    if lines and lines[0].strip().upper().startswith("TITLE:"):
        return "\n".join(lines[1:]).strip()
    return note_markdown.strip()
