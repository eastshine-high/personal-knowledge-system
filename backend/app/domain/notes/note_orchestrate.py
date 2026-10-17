"""build_session — 추출 → 텍스트 추림 → NoteSession.start 를 잇는 진입점.

"PDF + 범위 → 노트"의 연결 고리. 추출기/LLM은 설정(get_extractor/get_llm_client)에서 가져오되,
테스트에서는 주입할 수 있다. 추출은 여기서 1회만; 이후 refine/apply_edit은 세션에서.
"""
from __future__ import annotations

from dataclasses import dataclass

from ...infrastructure.extractors import get_extractor
from ..extractor import ExtractionResult, Highlight, LayoutExtractor
from ...infrastructure.llm_client import LLMClient
from ...infrastructure import get_llm_client
from .note_prepare import prepare_context
from .note_session import NoteSession, SessionConfig


@dataclass
class BuildSessionRequest:
    """build_session 호출 파라미터 — PDF 경로·페이지 범위·주제·생성일·가이드라인."""

    pdf_path: str
    page_range: tuple[int, int]
    topic: str
    created: str
    guideline: str | None = None
    note_count: int = 1
    user_preferred_guideline: str | None = None
    use_highlights: bool = False                       # 형광 가중치 반영 토글 (끄면 기존 동작)
    highlight_weights: dict[str, float] | None = None  # 색상→가중치(주입식, config 유래)


def _collect_highlights(result: ExtractionResult) -> list[Highlight]:
    """ExtractionResult에서 중복 없는 형광 표시를 수집. 순서 유지((text,color) 기준)."""
    seen: set[tuple[str, str]] = set()
    out: list[Highlight] = []
    for pe in result.pages:
        for h in pe.highlights:
            key = (h.text, h.color)
            if key not in seen:
                seen.add(key)
                out.append(h)
    return out


def build_session(
    req: BuildSessionRequest,
    *,
    extractor: LayoutExtractor | None = None,
    client: LLMClient | None = None,
) -> NoteSession:
    """추출 → 준비 → NoteSession.start 까지 실행하고 세션을 반환한다."""
    extractor = extractor or get_extractor()
    client = client or get_llm_client()
    result = extractor.extract(req.pdf_path, req.page_range)
    context = prepare_context(result)
    pages = [pe.page for pe in result.pages]
    highlights = _collect_highlights(result) if req.use_highlights else []
    config = SessionConfig(
        source=result.source,
        pages=pages,
        topic=req.topic,
        created=req.created,
        guideline=req.guideline,
        user_preferred_guideline=req.user_preferred_guideline,
        highlights=highlights or None,
        highlight_weights=req.highlight_weights,
    )
    session = NoteSession(client=client, context=context, config=config)
    session.start(note_count=req.note_count)
    return session
