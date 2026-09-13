"""FastAPI 요청/응답 Pydantic 스키마."""
from __future__ import annotations

from pydantic import BaseModel


class FigureResponse(BaseModel):
    embed_name: str
    caption: str


class NoteResponse(BaseModel):
    id: str
    title: str
    source: str
    pages: list[int]
    topic: str
    created: str
    body: str
    tags: list[str]
    figures: list[FigureResponse]
    markdown: str


class EventResponse(BaseModel):
    seq: int
    author: str
    action: str
    content: str


class SessionResponse(BaseModel):
    session_id: str
    notes: list[NoteResponse]
    events: list[EventResponse]


class CreateSessionRequest(BaseModel):
    pdf_path: str
    page_start: int
    page_end: int
    topic: str
    guideline: str | None = None
    note_count: int = 1
    user_preferred_guideline: str | None = None


class RefineRequest(BaseModel):
    instruction: str
    note_id: str | None = None


class EditRequest(BaseModel):
    body: str
    title: str | None = None
