"""자유 대화 비즈니스 로직 — 하이라이트 수집·사용량 변환·시스템 컨텐츠 빌드 (FastAPI import 없음)."""
from __future__ import annotations

import json as _json

from ..domain.extractor import Highlight
from ..infrastructure.llm_client import LLMUsage
from ..schemas import LLMUsageResponse

_HMARKER = "\n\n[HIGHLIGHTS_JSON]"
_MODAL_COST_PER_S = 0.000211  # Modal A10G GPU 추정 요금 ($/s)


def collect_page_highlights(page_extractions, use_highlights: bool) -> list[Highlight]:
    """use_highlights=True일 때만 페이지 추출물에서 중복 없는 형광 표시 수집((text,color) 기준)."""
    if not use_highlights:
        return []
    seen: set[tuple[str, str]] = set()
    out: list[Highlight] = []
    for pe in page_extractions:
        for h in pe.highlights:
            key = (h.text, h.color)
            if key not in seen:
                seen.add(key)
                out.append(h)
    return out


def build_usage_response(usage: LLMUsage | None) -> LLMUsageResponse | None:
    """LLMUsage → LLMUsageResponse 변환. usage가 None이거나 cost_usd 계산 불가면 cost_usd=None."""
    if not usage:
        return None
    cost = usage.cost_usd
    return LLMUsageResponse(
        model=usage.model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=round(cost, 6) if cost is not None else None,
    )


def build_sys_content(context_text: str, highlights: list[Highlight]) -> str:
    """context_text + (선택) highlights를 시스템 메시지 content로 조립.

    현재 [HIGHLIGHTS_JSON]은 텍스트 목록으로 직렬화(색/가중치 반영은 후속 작업).
    """
    if highlights:
        texts = [h.text for h in highlights]
        return context_text + _HMARKER + _json.dumps(texts, ensure_ascii=False)
    return context_text
