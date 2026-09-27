"""OCR 캐시 레이어 — page_extractions 테이블 기반 페이지별 캐시.

캐시 키: (pdf_file_id, page_num).
캐시 히트 시 extractor 미호출. 미스 페이지만 추출 후 저장.
"""
from __future__ import annotations

import dataclasses
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from ..domain.extractor import (
    BBox,
    Block,
    ExtractionResult,
    LayoutExtractor,
    PageExtraction,
)
from .extractors.base_extractor import ExtractionError


@dataclass
class ExtractionTarget:
    """get_or_extract 호출 파라미터 — 파일 ID·페이지 목록·PDF 경로."""

    pdf_file_id: str
    pages: list[int]
    pdf_path: str


@dataclass
class PageCacheKey:
    """캐시 저장 키 — (pdf_file_id, page_num)."""

    pdf_file_id: str
    page_num: int


# --- 직렬화 / 역직렬화 -------------------------------------------------------

def _page_to_dict(pe: PageExtraction) -> dict:
    return dataclasses.asdict(pe)


def _dict_to_page(d: dict) -> PageExtraction:
    blocks = [
        Block(
            type=b["type"],
            bbox=BBox(**b["bbox"]),
            reading_order=b["reading_order"],
            text=b["text"],
            image_ref=b["image_ref"],
        )
        for b in d["blocks"]
    ]
    return PageExtraction(
        page=d["page"],
        width_px=d["width_px"],
        height_px=d["height_px"],
        render_dpi=d["render_dpi"],
        blocks=blocks,
        highlights=d.get("highlights", []),
    )


# --- 캐시 조회/저장 ----------------------------------------------------------

def _load_cached(
    db: sqlite3.Connection, pdf_file_id: str, pages: list[int]
) -> dict[int, PageExtraction]:
    """DB에서 지정 페이지의 캐시된 추출 결과를 {page_num: PageExtraction} 맵으로 반환."""
    placeholders = ",".join("?" * len(pages))
    rows = db.execute(
        f"SELECT page_num, json FROM page_extractions "
        f"WHERE pdf_file_id = ? AND page_num IN ({placeholders})",
        (pdf_file_id, *pages),
    ).fetchall()
    return {row["page_num"]: _dict_to_page(json.loads(row["json"])) for row in rows}


def _save_page(db: sqlite3.Connection, key: PageCacheKey, pe: PageExtraction) -> None:
    """캐시에 단일 페이지 추출 결과를 저장한다."""
    db.execute(
        "INSERT OR REPLACE INTO page_extractions (pdf_file_id, page_num, json, created_at) "
        "VALUES (?, ?, ?, ?)",
        (key.pdf_file_id, key.page_num, json.dumps(_page_to_dict(pe)), datetime.now(timezone.utc).isoformat()),
    )
    db.commit()


# --- 공개 API ----------------------------------------------------------------

def get_or_extract(
    db: sqlite3.Connection,
    target: ExtractionTarget,
    extractor: LayoutExtractor,
) -> tuple[list[PageExtraction], int]:
    """pages 순서대로 (PageExtraction 목록, 실제 추출 수) 반환. 캐시 미스 페이지만 extractor 호출.

    두 번째 반환값이 0이면 전체 캐시 히트 (GPU/OCR 미호출).
    """
    cached = _load_cached(db, target.pdf_file_id, target.pages)
    result: dict[int, PageExtraction] = dict(cached)

    missing = [p for p in target.pages if p not in cached]
    for page_num in missing:
        try:
            extracted: ExtractionResult = extractor.extract(target.pdf_path, (page_num, page_num))
        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"페이지 {page_num} 추출 실패: {e}") from e
        if extracted.pages:
            pe = extracted.pages[0]
        else:
            pe = PageExtraction(page=page_num)
        try:
            _save_page(db, PageCacheKey(target.pdf_file_id, page_num), pe)
        except Exception as e:
            raise ExtractionError(f"페이지 {page_num} 캐시 저장 실패: {e}") from e
        result[page_num] = pe

    return [result[p] for p in target.pages if p in result], len(missing)
