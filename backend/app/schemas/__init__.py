"""공용 Pydantic 스키마 — 전체 re-export (기존 from app.schemas import ... 호환 유지)."""
from __future__ import annotations

from .library_schemas import BookCreate, BookResponse, PdfFileCreate, PdfFileResponse
from .chat_schemas import (
    ChatResponse,
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
    ExtractionStatsResponse,
    LLMUsageResponse,
    MessageCreate,
    MessageResponse,
)
from .notes_schemas import (
    CreateSessionRequest,
    EditRequest,
    EventResponse,
    FigureResponse,
    NoteResponse,
    RefineRequest,
    SessionResponse,
)
from .extraction_schemas import ExtractionCreate, ExtractionResponse

__all__ = [
    "BookCreate",
    "BookResponse",
    "PdfFileCreate",
    "PdfFileResponse",
    "ChatResponse",
    "ConversationCreate",
    "ConversationResponse",
    "ConversationUpdate",
    "ExtractionStatsResponse",
    "LLMUsageResponse",
    "MessageCreate",
    "MessageResponse",
    "ExtractionCreate",
    "ExtractionResponse",
    "CreateSessionRequest",
    "EditRequest",
    "EventResponse",
    "FigureResponse",
    "NoteResponse",
    "RefineRequest",
    "SessionResponse",
]
