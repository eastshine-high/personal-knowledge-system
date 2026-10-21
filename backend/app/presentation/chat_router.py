"""자유 대화 API — 대화 생성·조회·메시지 전송 (thin HTTP 핸들러)."""
from __future__ import annotations

import json as _json
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from ..application.chat_repository import (
    ChatExchange,
    load_history,
    now,
    persist_exchange,
    resolve_pdf_row,
    restore_context,
    row_to_conv,
    row_to_msg,
)
from ..application.chat_service import (
    _MODAL_COST_PER_S,
    build_sys_content,
    build_usage_response,
    collect_page_highlights,
)
from ..config import Settings, get_settings
from ..db import get_db
from ..domain.extractor import ExtractionResult, LayoutExtractor
from ..infrastructure import get_llm_client
from ..infrastructure.chat_prompt import build_chat_messages
from ..infrastructure.extractors import ExtractionError, get_extractor
from ..infrastructure.llm_client import LLMClient
from ..infrastructure.ocr_cache import ExtractionTarget, get_or_extract
from ..domain.notes.note_prepare import PreparedContext, prepare_context
from ..pages import format_pages, parse_pages
from ..schemas import (
    ChatResponse,
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
    ExtractionStatsResponse,
    LLMUsageResponse,
    MessageCreate,
    MessageResponse,
)

router = APIRouter(tags=["chat"])


def _settings_dep() -> Settings:
    return get_settings()


def _extractor_dep(settings: Annotated[Settings, Depends(_settings_dep)]) -> LayoutExtractor:
    return get_extractor(settings)


def _llm_dep(settings: Annotated[Settings, Depends(_settings_dep)]) -> LLMClient:
    return get_llm_client(settings)


@router.get("/books/{book_id}/conversations", response_model=list[ConversationResponse])
def list_conversations(book_id: str, db=Depends(get_db)):
    if not db.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone():
        raise HTTPException(status_code=404, detail="책 없음")
    rows = db.execute(
        "SELECT * FROM conversations WHERE book_id = ? ORDER BY created_at DESC",
        (book_id,),
    ).fetchall()
    return [row_to_conv(r) for r in rows]


@router.post("/books/{book_id}/conversations", response_model=ConversationResponse, status_code=201)
def create_conversation(
    book_id: str,
    req: ConversationCreate,
    db=Depends(get_db),
    extractor: Annotated[LayoutExtractor, Depends(_extractor_dep)] = None,
    settings: Annotated[Settings, Depends(_settings_dep)] = None,
):
    pdf_row, missing = resolve_pdf_row(db, book_id, req.pdf_file_id)
    if pdf_row is None:
        detail = "책 없음" if missing == "책" else "PDF 파일 없음"
        raise HTTPException(status_code=404, detail=detail)
    try:
        pages = parse_pages(req.pages_str)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    t0 = time.monotonic()
    try:
        page_extractions, newly_extracted = get_or_extract(
            db,
            ExtractionTarget(pdf_file_id=req.pdf_file_id, pages=pages, pdf_path=pdf_row["pdf_path"]),
            extractor,
        )
    except ExtractionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    elapsed = time.monotonic() - t0

    modal_cost = round(elapsed * _MODAL_COST_PER_S, 5) if settings.extract_backend.lower() == "modal" and newly_extracted > 0 else None
    extraction_stats = ExtractionStatsResponse(
        page_count=len(page_extractions), elapsed_s=round(elapsed, 2),
        backend=settings.extract_backend, cost_usd=modal_cost,
    )

    context: PreparedContext = prepare_context(ExtractionResult(source=pdf_row["pdf_path"], pages=page_extractions))
    highlights = collect_page_highlights(page_extractions, req.use_highlights)

    conv_id, n = str(uuid.uuid4()), now()
    db.execute(
        "INSERT INTO conversations (id, book_id, pdf_file_id, pages_json, title, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (conv_id, book_id, req.pdf_file_id, _json.dumps(pages), None, n),
    )
    sys_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?,?,?,?,?)",
        (sys_id, conv_id, "system", build_sys_content(context.text, highlights, settings.highlight_color_weights), n),
    )
    db.commit()
    return ConversationResponse(
        id=conv_id, book_id=book_id, pdf_file_id=req.pdf_file_id,
        pages=pages, pages_display=format_pages(pages), title=None, created_at=n,
        extraction_stats=extraction_stats,
    )


@router.patch("/conversations/{conv_id}", response_model=ConversationResponse)
def update_conversation(conv_id: str, req: ConversationUpdate, db=Depends(get_db)):
    """대화 주제(topic)를 수정한다."""
    if not db.execute("SELECT 1 FROM conversations WHERE id = ?", (conv_id,)).fetchone():
        raise HTTPException(status_code=404, detail="대화 없음")
    db.execute("UPDATE conversations SET topic = ? WHERE id = ?", (req.topic, conv_id))
    db.commit()
    row = db.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    return row_to_conv(row)


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageResponse])
def get_messages(conv_id: str, db=Depends(get_db)):
    if not db.execute("SELECT 1 FROM conversations WHERE id = ?", (conv_id,)).fetchone():
        raise HTTPException(status_code=404, detail="대화 없음")
    rows = db.execute(
        "SELECT * FROM messages WHERE conversation_id = ? AND role != 'system' ORDER BY created_at",
        (conv_id,),
    ).fetchall()
    return [row_to_msg(r) for r in rows]


@router.post("/conversations/{conv_id}/messages", response_model=ChatResponse)
def send_message(
    conv_id: str,
    req: MessageCreate,
    db=Depends(get_db),
    client: Annotated[LLMClient, Depends(_llm_dep)] = None,
):
    conv_row = db.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    if not conv_row:
        raise HTTPException(status_code=404, detail="대화 없음")

    context_text, highlights = restore_context(db, conv_id)
    history = load_history(db, conv_id)
    history.append({"role": "user", "content": req.content})

    messages = build_chat_messages(context_text, history, highlights or None)
    llm_resp = client.complete(messages)
    assistant_text = llm_resp.text

    n = now()
    asst_id = persist_exchange(db, ChatExchange(
        conv_id=conv_id,
        user_content=req.content,
        assistant_text=assistant_text,
        now=n,
        had_title=bool(conv_row["title"]),
        had_topic=bool(conv_row["topic"]),
    ))

    pages = _json.loads(conv_row["pages_json"])
    auto = req.content[:20].strip()
    conv_resp = ConversationResponse(
        id=conv_id, book_id=conv_row["book_id"], pdf_file_id=conv_row["pdf_file_id"],
        pages=pages, pages_display=format_pages(pages),
        title=conv_row["title"] or auto,
        topic=conv_row["topic"] or auto,
        created_at=conv_row["created_at"],
    )
    msg_resp = MessageResponse(
        id=asst_id, conversation_id=conv_id, role="assistant",
        content=assistant_text, created_at=n,
    )
    return ChatResponse(conversation=conv_resp, message=msg_resp, usage=build_usage_response(llm_resp.usage))
