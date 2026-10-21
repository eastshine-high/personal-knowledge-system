"""자유 대화 관련 Pydantic 스키마."""
from __future__ import annotations

from pydantic import BaseModel


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
    topic: str | None = None
    created_at: str
    extraction_stats: ExtractionStatsResponse | None = None


class ConversationCreate(BaseModel):
    pdf_file_id: str
    pages_str: str          # "10-15, 21" 형식
    use_highlights: bool = False


class ConversationUpdate(BaseModel):
    topic: str


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
