"""FastAPI 요청/응답 Pydantic 스키마."""
from __future__ import annotations

from pydantic import BaseModel


# --- 서재 -------------------------------------------------------------------

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


# --- 자유 대화 ---------------------------------------------------------------

class LLMUsageResponse(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None = None


class ExtractionStatsResponse(BaseModel):
    page_count: int
    elapsed_s: float
    backend: str
    cost_usd: float | None = None   # Modal 추정 비용 (A10G ~$0.000211/s)


class ConversationResponse(BaseModel):
    id: str
    book_id: str
    pdf_file_id: str
    pages: list[int]
    pages_display: str      # "p.10-15, 21"
    title: str | None
    created_at: str
    extraction_stats: ExtractionStatsResponse | None = None


class ConversationCreate(BaseModel):
    pdf_file_id: str
    pages_str: str          # "10-15, 21" 형식
    use_highlights: bool = False


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str               # "user" | "assistant"
    content: str
    created_at: str


class MessageCreate(BaseModel):
    content: str


class ChatResponse(BaseModel):
    conversation: ConversationResponse
    message: MessageResponse
    usage: LLMUsageResponse | None = None


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
