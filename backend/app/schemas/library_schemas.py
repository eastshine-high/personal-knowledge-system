"""서재 관련 Pydantic 스키마 — BookResponse, PdfFileResponse, BookCreate, PdfFileCreate."""
from __future__ import annotations

from pydantic import BaseModel


class PdfFileResponse(BaseModel):
    id: str
    book_id: str
    label: str
    pdf_path: str
    created_at: str


class BookResponse(BaseModel):
    id: str
    title: str
    created_at: str
    pdf_files: list[PdfFileResponse] = []


class BookCreate(BaseModel):
    title: str


class PdfFileCreate(BaseModel):
    label: str
    pdf_path: str
