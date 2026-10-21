"""추출 세트(주제별 OCR 범위) 관련 Pydantic 스키마."""
from __future__ import annotations

from pydantic import BaseModel


class ExtractionCreate(BaseModel):
    topic: str
    pages_str: str          # "10-15, 21" 형식


class ExtractionResponse(BaseModel):
    id: str
    pdf_file_id: str
    topic: str
    pages: list[int]
    pages_display: str      # "p.10-15, 21"
    created_at: str
