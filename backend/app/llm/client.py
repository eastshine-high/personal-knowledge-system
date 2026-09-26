"""범용 LLMClient — 공급자 독립 채팅 인터페이스 ("그냥 LLM").

요약/리파인 같은 작업 로직은 여기 두지 않는다(그건 notes의 프롬프트 빌더). 여기는 순수 전송:
messages(list[Message]) → text. 공급자는 mock | anthropic | openai호환 | local 로 스왑.
"""
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


# --- Mock (결정적, 오프라인 기본) -----------------------------------------

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


# --- Anthropic ---------------------------------------------------------------

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
