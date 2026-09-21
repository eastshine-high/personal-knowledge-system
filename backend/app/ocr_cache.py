"""OCR 캐시 레이어 — page_extractions 테이블 기반 페이지별 캐시.

캐시 키: (pdf_file_id, page_num).
캐시 히트 시 extractor 미호출. 미스 페이지만 추출 후 저장.
"""
from __future__ import annotations

import dataclasses
import json
import sqlite3
from datetime import datetime, timezone

from .extractor import (
    BBox,
    Block,
    ExtractionResult,
    LayoutExtractor,
    PageExtraction,
)


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
    )


# --- 캐시 조회/저장 ----------------------------------------------------------

def _load_cached(
    db: sqlite3.Connection, pdf_file_id: str, pages: list[int]
) -> dict[int, PageExtraction]:
    placeholders = ",".join("?" * len(pages))
    rows = db.execute(
        f"SELECT page_num, json FROM page_extractions "
        f"WHERE pdf_file_id = ? AND page_num IN ({placeholders})",
        (pdf_file_id, *pages),
    ).fetchall()
    return {row["page_num"]: _dict_to_page(json.loads(row["json"])) for row in rows}


def _save_page(
    db: sqlite3.Connection, pdf_file_id: str, page_num: int, pe: PageExtraction
) -> None:
    db.execute(
        "INSERT OR REPLACE INTO page_extractions (pdf_file_id, page_num, json, created_at) "
        "VALUES (?, ?, ?, ?)",
        (pdf_file_id, page_num, json.dumps(_page_to_dict(pe)), datetime.now(timezone.utc).isoformat()),
    )
    db.commit()


# --- 공개 API ----------------------------------------------------------------

def get_or_extract(
    db: sqlite3.Connection,
    pdf_file_id: str,
    pages: list[int],
    pdf_path: str,
    extractor: LayoutExtractor,
) -> list[PageExtraction]:
    """pages 순서대로 PageExtraction 반환. 캐시 미스 페이지만 extractor 호출."""
    cached = _load_cached(db, pdf_file_id, pages)
    result: dict[int, PageExtraction] = dict(cached)

    missing = [p for p in pages if p not in cached]
    for page_num in missing:
        extracted: ExtractionResult = extractor.extract(pdf_path, (page_num, page_num))
        if extracted.pages:
            pe = extracted.pages[0]
        else:
            pe = PageExtraction(page=page_num)
        _save_page(db, pdf_file_id, page_num, pe)
        result[page_num] = pe

    return [result[p] for p in pages if p in result]
