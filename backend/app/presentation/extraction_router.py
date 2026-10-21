"""추출 세트 API — 주제별 OCR 범위 생성·조회·삭제 (thin HTTP 핸들러)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from ..application.chat_repository import resolve_pdf_row
from ..application.extraction_repository import (
    delete_extraction,
    insert_extraction,
    list_extractions,
)
from ..config import Settings, get_settings
from ..db import get_db
from ..domain.extractor import LayoutExtractor
from ..infrastructure.extractors import ExtractionError, get_extractor
from ..infrastructure.ocr_cache import ExtractionTarget, get_or_extract
from ..pages import parse_pages
from ..schemas import ExtractionCreate, ExtractionResponse

router = APIRouter(tags=["extraction"])


def _settings_dep() -> Settings:
    return get_settings()


def _extractor_dep(settings: Annotated[Settings, Depends(_settings_dep)]) -> LayoutExtractor:
    return get_extractor(settings)


def _require_pdf(db, book_id: str, pdf_id: str):
    """book+pdf 존재 검증. 없으면 404, 있으면 pdf_row 반환."""
    pdf_row, missing = resolve_pdf_row(db, book_id, pdf_id)
    if pdf_row is None:
        raise HTTPException(status_code=404, detail="책 없음" if missing == "책" else "PDF 파일 없음")
    return pdf_row


@router.post(
    "/books/{book_id}/pdfs/{pdf_id}/extractions",
    response_model=ExtractionResponse, status_code=201,
)
def create_extraction(
    book_id: str,
    pdf_id: str,
    req: ExtractionCreate,
    db=Depends(get_db),
    extractor: Annotated[LayoutExtractor, Depends(_extractor_dep)] = None,
):
    """주제+페이지 범위 → 범위 OCR(미캐시만) 후 추출 세트 생성."""
    pdf_row = _require_pdf(db, book_id, pdf_id)
    try:
        pages = parse_pages(req.pages_str)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    try:
        get_or_extract(
            db,
            ExtractionTarget(pdf_file_id=pdf_id, pages=pages, pdf_path=pdf_row["pdf_path"]),
            extractor,
        )
    except ExtractionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return insert_extraction(db, pdf_id, req.topic, pages)


@router.get(
    "/books/{book_id}/pdfs/{pdf_id}/extractions",
    response_model=list[ExtractionResponse],
)
def get_extractions(book_id: str, pdf_id: str, db=Depends(get_db)):
    """해당 PDF의 추출 세트 목록."""
    _require_pdf(db, book_id, pdf_id)
    return list_extractions(db, pdf_id)


@router.delete(
    "/books/{book_id}/pdfs/{pdf_id}/extractions/{extraction_id}", status_code=204,
)
def remove_extraction(book_id: str, pdf_id: str, extraction_id: str, db=Depends(get_db)):
    """추출 세트 삭제(page_extractions 공유 캐시는 보존)."""
    if not delete_extraction(db, extraction_id):
        raise HTTPException(status_code=404, detail="추출 세트 없음")
