"""추출 세트 DB 쿼리 — 주제별 OCR 범위 기록 (FastAPI import 없음)."""
from __future__ import annotations

import json as _json
import uuid

from ..pages import format_pages
from ..schemas import ExtractionResponse
from .chat_repository import now


def row_to_extraction(row) -> ExtractionResponse:
    """DB 행을 ExtractionResponse로 변환."""
    pages = _json.loads(row["pages_json"])
    return ExtractionResponse(
        id=row["id"], pdf_file_id=row["pdf_file_id"], topic=row["topic"],
        pages=pages, pages_display=format_pages(pages), created_at=row["created_at"],
    )


def insert_extraction(db, pdf_file_id: str, topic: str, pages: list[int]) -> ExtractionResponse:
    """추출 세트 1건을 저장하고 ExtractionResponse 반환."""
    ext_id, n = str(uuid.uuid4()), now()
    db.execute(
        "INSERT INTO extractions (id, pdf_file_id, topic, pages_json, created_at) VALUES (?,?,?,?,?)",
        (ext_id, pdf_file_id, topic, _json.dumps(pages), n),
    )
    db.commit()
    return ExtractionResponse(
        id=ext_id, pdf_file_id=pdf_file_id, topic=topic,
        pages=pages, pages_display=format_pages(pages), created_at=n,
    )


def list_extractions(db, pdf_file_id: str) -> list[ExtractionResponse]:
    """해당 PDF의 추출 세트 목록(최신순) 반환."""
    rows = db.execute(
        "SELECT * FROM extractions WHERE pdf_file_id = ? ORDER BY created_at DESC", (pdf_file_id,)
    ).fetchall()
    return [row_to_extraction(r) for r in rows]


def delete_extraction(db, extraction_id: str) -> bool:
    """추출 세트 삭제(page_extractions 공유 캐시는 보존). 삭제 성공 여부 반환."""
    cur = db.execute("DELETE FROM extractions WHERE id = ?", (extraction_id,))
    db.commit()
    return cur.rowcount > 0
