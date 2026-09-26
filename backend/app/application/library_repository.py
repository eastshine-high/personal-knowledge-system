"""서재 DB 쿼리 — 책·PDF 조회 (FastAPI import 없음)."""
from __future__ import annotations

from .chat_repository import now
from ..schemas import BookResponse, PdfFileResponse


def row_to_pdf(row) -> PdfFileResponse:
    """DB 행을 PdfFileResponse로 변환."""
    return PdfFileResponse(
        id=row["id"], book_id=row["book_id"], label=row["label"],
        pdf_path=row["pdf_path"], created_at=row["created_at"],
    )


def book_with_pdfs(db, book_row) -> BookResponse:
    """book_row와 연결된 PDF 파일 목록을 포함한 BookResponse 반환."""
    pdfs = db.execute(
        "SELECT * FROM pdf_files WHERE book_id = ? ORDER BY created_at", (book_row["id"],)
    ).fetchall()
    return BookResponse(
        id=book_row["id"], title=book_row["title"], created_at=book_row["created_at"],
        pdf_files=[row_to_pdf(r) for r in pdfs],
    )
