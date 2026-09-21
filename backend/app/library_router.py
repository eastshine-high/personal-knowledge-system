"""서재 API — 책·PDF 파일 CRUD."""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from .db import get_db
from .schemas import BookCreate, BookResponse, PdfFileCreate, PdfFileResponse

router = APIRouter(prefix="/books", tags=["library"])


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def _row_to_pdf(row) -> PdfFileResponse:
    return PdfFileResponse(
        id=row["id"], book_id=row["book_id"], label=row["label"],
        pdf_path=row["pdf_path"], created_at=row["created_at"],
    )


def _book_with_pdfs(db, book_row) -> BookResponse:
    pdfs = db.execute(
        "SELECT * FROM pdf_files WHERE book_id = ? ORDER BY created_at", (book_row["id"],)
    ).fetchall()
    return BookResponse(
        id=book_row["id"], title=book_row["title"], created_at=book_row["created_at"],
        pdf_files=[_row_to_pdf(r) for r in pdfs],
    )


@router.get("", response_model=list[BookResponse])
def list_books(db=Depends(get_db)):
    rows = db.execute("SELECT * FROM books ORDER BY created_at DESC").fetchall()
    return [_book_with_pdfs(db, r) for r in rows]


@router.post("", response_model=BookResponse, status_code=201)
def create_book(req: BookCreate, db=Depends(get_db)):
    book_id = str(uuid.uuid4())
    now = _now()
    db.execute("INSERT INTO books (id, title, created_at) VALUES (?, ?, ?)",
               (book_id, req.title, now))
    db.commit()
    return BookResponse(id=book_id, title=req.title, created_at=now, pdf_files=[])


@router.post("/{book_id}/pdfs", response_model=PdfFileResponse, status_code=201)
def add_pdf(book_id: str, req: PdfFileCreate, db=Depends(get_db)):
    if not db.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone():
        raise HTTPException(status_code=404, detail="책 없음")
    if not Path(req.pdf_path).is_file():
        raise HTTPException(status_code=404, detail=f"PDF 파일 없음: {req.pdf_path}")
    pdf_id = str(uuid.uuid4())
    now = _now()
    db.execute(
        "INSERT INTO pdf_files (id, book_id, label, pdf_path, created_at) VALUES (?,?,?,?,?)",
        (pdf_id, book_id, req.label, req.pdf_path, now),
    )
    db.commit()
    return PdfFileResponse(id=pdf_id, book_id=book_id, label=req.label,
                           pdf_path=req.pdf_path, created_at=now)


@router.delete("/{book_id}/pdfs/{pdf_id}", status_code=204)
def delete_pdf(book_id: str, pdf_id: str, db=Depends(get_db)):
    row = db.execute(
        "SELECT 1 FROM pdf_files WHERE id = ? AND book_id = ?", (pdf_id, book_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="PDF 파일 없음")
    db.execute("DELETE FROM pdf_files WHERE id = ?", (pdf_id,))
    db.commit()
