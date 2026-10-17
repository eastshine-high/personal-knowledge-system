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


def build_sys_content(
    context_text: str, highlights: list[Highlight], weights: dict[str, float] | None = None
) -> str:
    """context_text + (선택) highlights를 시스템 메시지 content로 조립.

    [HIGHLIGHTS_JSON]에 {text,color,weight}로 직렬화 — 가중치를 생성 시점에 구워넣어
    이후 프롬프트 빌드가 settings 없이 그룹핑하게 한다.
    """
    if highlights:
        w = weights or {}
        payload = [{"text": h.text, "color": h.color, "weight": w.get(h.color, 1.0)} for h in highlights]
        return context_text + _HMARKER + _json.dumps(payload, ensure_ascii=False)
    return context_text
