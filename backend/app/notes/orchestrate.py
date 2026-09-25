"""build_session — 추출 → 텍스트 추림 → NoteSession.start 를 잇는 진입점.

"PDF + 범위 → 노트"의 연결 고리. 추출기/LLM은 설정(get_extractor/get_llm_client)에서 가져오되,
테스트에서는 주입할 수 있다. 추출은 여기서 1회만; 이후 refine/apply_edit은 세션에서.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..extractors import get_extractor
from ..extractor import ExtractionResult, LayoutExtractor
from ..llm import LLMClient, get_llm_client
from .prepare import prepare_context
from .session import NoteSession, SessionConfig


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


def _collect_highlights(result: ExtractionResult) -> list[str]:
    """ExtractionResult에서 중복 없는 형광 표시 텍스트를 수집. 순서 유지."""
    seen: set[str] = set()
    out: list[str] = []
    for pe in result.pages:
        for h in pe.highlights:
            if h not in seen:
                seen.add(h)
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
    highlights = _collect_highlights(result)
    config = SessionConfig(
        source=result.source,
        pages=pages,
        topic=req.topic,
        created=req.created,
        guideline=req.guideline,
        user_preferred_guideline=req.user_preferred_guideline,
        highlights=highlights or None,
    )
    session = NoteSession(client=client, context=context, config=config)
    session.start(note_count=req.note_count)
    return session
