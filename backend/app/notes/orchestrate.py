"""build_session — 추출 → 텍스트 추림 → NoteSession.start 를 잇는 진입점.

"PDF + 범위 → 노트"의 연결 고리. 추출기/LLM은 설정(get_extractor/get_llm_client)에서 가져오되,
테스트에서는 주입할 수 있다. 추출은 여기서 1회만; 이후 refine/apply_edit은 세션에서.
"""
from __future__ import annotations

from ..extractors import get_extractor
from ..extractor import LayoutExtractor
from ..llm import LLMClient, get_llm_client
from .prepare import prepare_context
from .session import NoteSession


def build_session(
    pdf_path: str,
    page_range: tuple[int, int],
    *,
    topic: str,
    created: str,
    guideline: str | None = None,
    note_count: int = 1,
    user_preferred_guideline: str | None = None,
    extractor: LayoutExtractor | None = None,
    client: LLMClient | None = None,
) -> NoteSession:
    """추출 → 준비 → NoteSession.start 까지 실행하고 세션을 반환한다."""
    extractor = extractor or get_extractor()
    client = client or get_llm_client()

    result = extractor.extract(pdf_path, page_range)
    context = prepare_context(result)
    pages = [pe.page for pe in result.pages]  # 실제 추출된 페이지들

    seen_h: set[str] = set()
    all_highlights: list[str] = []
    for pe in result.pages:
        for h in pe.highlights:
            if h not in seen_h:
                seen_h.add(h)
                all_highlights.append(h)

    session = NoteSession(
        client=client,
        context=context,
        source=result.source,
        pages=pages,
        topic=topic,
        guideline=guideline,
        created=created,
        user_preferred_guideline=user_preferred_guideline,
        highlights=all_highlights or None,
    )
    session.start(note_count=note_count)
    return session
