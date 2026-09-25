"""텍스트 추림 + 그림↔캡션 페어링 (PII 경계).

`ExtractionResult`(추출기 산출)를 받아:
  - text    : 모든 블록을 (page, bbox.y) 시각 읽기순서로 정렬한 뒤 **텍스트성 블록만** 이어붙임 (LLM으로 보낼 것)
  - figures : 각 figure를 최근접 figure_caption과 페어링한 Figure{crop, caption, anchor}

figure는 reading_order=None(텍스트 시퀀스 밖)이라, 위치(bbox.y)로 스트림에 끼워 넣어 순서를 보존한다.
LLM에는 `text`만 전달한다(이미지/bbox/경로 미전송) → PII 경계.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..extractor import BBox, Block, ExtractionResult

# 요약 컨텍스트에 기여하는 텍스트성 블록 (header/footer/number/figure/figure_caption/other 제외)
CONTENT_TYPES = {"text", "title", "formula", "code"}


@dataclass
class PreparedFigure:
    """페어링된 그림 — 원본 크롭 경로 + 캡션 + 위치 앵커."""

    source_path: str     # figure 크롭 image_ref ("" = 크롭 실패)
    caption: str         # 페어링된 캡션 텍스트 ("" = 캡션 없음)
    page: int
    anchor_index: int    # 이 그림 앞에 온 텍스트 조각 수 = 노트 배치 힌트
    bbox: BBox


@dataclass
class PreparedContext:
    """LLM에 보낼 텍스트 + 첨부 후보 그림."""

    text: str
    figures: list[PreparedFigure] = field(default_factory=list)


def _nearest_caption(
    fig: Block, captions: list[Block], used: set[int], threshold_px: float
) -> str:
    """figure에 세로로 가장 가까운(대개 바로 아래) 미사용 캡션을 반환. 임계값 초과면 ""."""
    best: Block | None = None
    best_d: float | None = None
    for c in captions:
        if id(c) in used:
            continue
        if c.bbox.y0 >= fig.bbox.y1:        # 캡션이 그림 아래
            d = c.bbox.y0 - fig.bbox.y1
        elif c.bbox.y1 <= fig.bbox.y0:      # 캡션이 그림 위
            d = fig.bbox.y0 - c.bbox.y1
        else:                                # 세로로 겹침
            d = 0.0
        if best_d is None or d < best_d:
            best, best_d = c, d
    if best is not None and best_d is not None and best_d <= threshold_px:
        used.add(id(best))
        return best.text.strip()
    return ""


def _collect_captions_by_page(
    ordered: list[tuple[int, Block]],
) -> dict[int, list[Block]]:
    """ordered 블록 목록에서 figure_caption을 페이지별로 그룹화."""
    result: dict[int, list[Block]] = {}
    for page, b in ordered:
        if b.type == "figure_caption":
            result.setdefault(page, []).append(b)
    return result


def _iter_content(
    ordered: list[tuple[int, Block]],
    captions_by_page: dict[int, list[Block]],
    threshold_px: float,
) -> tuple[list[str], list[PreparedFigure]]:
    """ordered 블록을 순회해 텍스트 조각과 figure 목록을 수집."""
    used_captions: set[int] = set()
    text_parts: list[str] = []
    figures: list[PreparedFigure] = []
    for page, b in ordered:
        if b.type in CONTENT_TYPES and b.text.strip():
            text_parts.append(b.text.strip())
        elif b.type == "figure":
            caption = _nearest_caption(
                b, captions_by_page.get(page, []), used_captions, threshold_px
            )
            figures.append(PreparedFigure(
                source_path=b.image_ref or "",
                caption=caption,
                page=page,
                anchor_index=len(text_parts),
                bbox=b.bbox,
            ))
    return text_parts, figures


def prepare_context(
    result: ExtractionResult, *, caption_gap_threshold_px: float = 250.0
) -> PreparedContext:
    """ExtractionResult → (LLM용 텍스트, 페어링된 figure 목록)."""
    ordered: list[tuple[int, Block]] = sorted(
        [(pe.page, b) for pe in result.pages for b in pe.blocks],
        key=lambda pb: (pb[0], pb[1].bbox.y0),
    )
    captions_by_page = _collect_captions_by_page(ordered)
    text_parts, figures = _iter_content(ordered, captions_by_page, caption_gap_threshold_px)
    return PreparedContext(text="\n\n".join(text_parts), figures=figures)
