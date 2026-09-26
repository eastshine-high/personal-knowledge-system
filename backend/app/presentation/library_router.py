"""서재 API — 책·PDF 파일 CRUD (thin HTTP 핸들러)."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..application.chat_repository import now
from ..application.library_repository import book_with_pdfs, row_to_pdf
from ..db import get_db
from ..schemas import BookCreate, BookResponse, PdfFileCreate, PdfFileResponse

router = APIRouter(prefix="/books", tags=["library"])


@router.get("", response_model=list[BookResponse])
def list_books(db=Depends(get_db)):
    rows = db.execute("SELECT * FROM books ORDER BY created_at DESC").fetchall()
    return [book_with_pdfs(db, r) for r in rows]


@router.post("", response_model=BookResponse, status_code=201)
def create_book(req: BookCreate, db=Depends(get_db)):
    book_id = str(uuid.uuid4())
    n = now()
    db.execute("INSERT INTO books (id, title, created_at) VALUES (?, ?, ?)",
               (book_id, req.title, n))
    db.commit()
    return BookResponse(id=book_id, title=req.title, created_at=n, pdf_files=[])


@router.post("/{book_id}/pdfs", response_model=PdfFileResponse, status_code=201)
def add_pdf(book_id: str, req: PdfFileCreate, db=Depends(get_db)):
    if not db.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone():
        raise HTTPException(status_code=404, detail="책 없음")
    if not Path(req.pdf_path).is_file():
        raise HTTPException(status_code=404, detail=f"PDF 파일 없음: {req.pdf_path}")
    pdf_id = str(uuid.uuid4())
    n = now()
    db.execute(
        "INSERT INTO pdf_files (id, book_id, label, pdf_path, created_at) VALUES (?,?,?,?,?)",
        (pdf_id, book_id, req.label, req.pdf_path, n),
    )
    db.commit()
    return PdfFileResponse(id=pdf_id, book_id=book_id, label=req.label,
                           pdf_path=req.pdf_path, created_at=n)


@router.delete("/{book_id}/pdfs/{pdf_id}", status_code=204)
def delete_pdf(book_id: str, pdf_id: str, db=Depends(get_db)):
    row = db.execute(
        "SELECT 1 FROM pdf_files WHERE id = ? AND book_id = ?", (pdf_id, book_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="PDF 파일 없음")
    db.execute("DELETE FROM pdf_files WHERE id = ?", (pdf_id,))
    db.commit()
