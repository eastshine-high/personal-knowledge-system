"""자유 대화 API — 대화 생성·조회·메시지 전송."""
from __future__ import annotations

import json as _json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from .config import Settings, get_settings
from .db import get_db
from .extractor import ExtractionResult, LayoutExtractor
from .extractors import get_extractor
from .extractors.base import ExtractionError
from .llm import LLMClient, LLMUsage, get_llm_client
from .llm.chat_prompt import build_chat_messages
from .notes.prepare import PreparedContext, prepare_context
from .ocr_cache import ExtractionTarget, get_or_extract
from .pages import format_pages, parse_pages
from .schemas import (
    ChatResponse,
    ConversationCreate,
    ConversationResponse,
    ExtractionStatsResponse,
    LLMUsageResponse,
    MessageCreate,
    MessageResponse,
)

router = APIRouter(tags=["chat"])

_HMARKER = "\n\n[HIGHLIGHTS_JSON]"


@dataclass
class ChatExchange:
    """_persist_exchange 호출 파라미터 — 대화 ID·user/assistant 메시지·타임스탬프·제목 여부."""

    conv_id: str
    user_content: str
    assistant_text: str
    now: str
    had_title: bool


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _settings_dep() -> Settings:
    return get_settings()


def _extractor_dep(settings: Annotated[Settings, Depends(_settings_dep)]) -> LayoutExtractor:
    return get_extractor(settings)


def _llm_dep(settings: Annotated[Settings, Depends(_settings_dep)]) -> LLMClient:
    return get_llm_client(settings)


def _row_to_conv(row) -> ConversationResponse:
    pages = _json.loads(row["pages_json"])
    return ConversationResponse(
        id=row["id"],
        book_id=row["book_id"],
        pdf_file_id=row["pdf_file_id"],
        pages=pages,
        pages_display=format_pages(pages),
        title=row["title"],
        created_at=row["created_at"],
    )


def _row_to_msg(row) -> MessageResponse:
    return MessageResponse(
        id=row["id"],
        conversation_id=row["conversation_id"],
        role=row["role"],
        content=row["content"],
        created_at=row["created_at"],
    )


def _resolve_pdf_row(db, book_id: str, pdf_file_id: str):
    """book + pdf 존재 검증 후 pdf_row 반환. 없으면 HTTPException."""
    if not db.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone():
        raise HTTPException(status_code=404, detail="책 없음")
    row = db.execute(
        "SELECT * FROM pdf_files WHERE id = ? AND book_id = ?",
        (pdf_file_id, book_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="PDF 파일 없음")
    return row


def _collect_page_highlights(page_extractions, use_highlights: bool) -> list[str]:
    """use_highlights=True일 때만 페이지 추출물에서 중복 없는 형광 텍스트 수집."""
    if not use_highlights:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for pe in page_extractions:
        for h in pe.highlights:
            if h not in seen:
                seen.add(h)
                out.append(h)
    return out


_MODAL_COST_PER_S = 0.000211  # Modal A10G GPU 추정 요금 ($/s)


def _build_usage_response(usage: LLMUsage | None) -> LLMUsageResponse | None:
    """LLMUsage → LLMUsageResponse 변환. usage가 None이거나 cost_usd 계산 불가면 cost_usd=None."""
    if not usage:
        return None
    cost = usage.cost_usd
    return LLMUsageResponse(
        model=usage.model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=round(cost, 6) if cost is not None else None,
    )


def _build_sys_content(context_text: str, highlights: list[str]) -> str:
    """context_text + (선택) highlights를 시스템 메시지 content로 조립."""
    if highlights:
        return context_text + _HMARKER + _json.dumps(highlights, ensure_ascii=False)
    return context_text


def _restore_context(db, conv_id: str) -> tuple[str, list[str]]:
    """system 메시지에서 context_text와 highlights를 복원."""
    sys_row = db.execute(
        "SELECT content FROM messages WHERE conversation_id = ? AND role = 'system' LIMIT 1",
        (conv_id,),
    ).fetchone()
    raw_sys = sys_row["content"] if sys_row else ""
    if _HMARKER in raw_sys:
        parts = raw_sys.split(_HMARKER, 1)
        try:
            return parts[0], _json.loads(parts[1])
        except (ValueError, IndexError):
            return parts[0], []
    return raw_sys, []


def _load_history(db, conv_id: str) -> list[dict]:
    """대화의 user/assistant 메시지 이력을 시간순으로 반환."""
    rows = db.execute(
        "SELECT role, content FROM messages "
        "WHERE conversation_id = ? AND role != 'system' ORDER BY created_at",
        (conv_id,),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def _persist_exchange(db, exchange: ChatExchange) -> str:
    """user + assistant 메시지 저장. 첫 메시지면 대화 제목도 설정. assistant message id 반환."""
    user_id, asst_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.execute(
        "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?,?,?,?,?)",
        (user_id, exchange.conv_id, "user", exchange.user_content, exchange.now),
    )
    db.execute(
        "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?,?,?,?,?)",
        (asst_id, exchange.conv_id, "assistant", exchange.assistant_text, exchange.now),
    )
    if not exchange.had_title:
        db.execute("UPDATE conversations SET title = ? WHERE id = ?", (exchange.user_content[:20].strip(), exchange.conv_id))
    db.commit()
    return asst_id


@router.get("/books/{book_id}/conversations", response_model=list[ConversationResponse])
def list_conversations(book_id: str, db=Depends(get_db)):
    if not db.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone():
        raise HTTPException(status_code=404, detail="책 없음")
    rows = db.execute(
        "SELECT * FROM conversations WHERE book_id = ? ORDER BY created_at DESC",
        (book_id,),
    ).fetchall()
    return [_row_to_conv(r) for r in rows]


@router.post("/books/{book_id}/conversations", response_model=ConversationResponse, status_code=201)
def create_conversation(
    book_id: str,
    req: ConversationCreate,
    db=Depends(get_db),
    extractor: Annotated[LayoutExtractor, Depends(_extractor_dep)] = None,
    settings: Annotated[Settings, Depends(_settings_dep)] = None,
):
    pdf_row = _resolve_pdf_row(db, book_id, req.pdf_file_id)
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
    highlights = _collect_page_highlights(page_extractions, req.use_highlights)

    conv_id, now = str(uuid.uuid4()), _now()
    db.execute(
        "INSERT INTO conversations (id, book_id, pdf_file_id, pages_json, title, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (conv_id, book_id, req.pdf_file_id, _json.dumps(pages), None, now),
    )
    sys_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?,?,?,?,?)",
        (sys_id, conv_id, "system", _build_sys_content(context.text, highlights), now),
    )
    db.commit()
    return ConversationResponse(
        id=conv_id, book_id=book_id, pdf_file_id=req.pdf_file_id,
        pages=pages, pages_display=format_pages(pages), title=None, created_at=now,
        extraction_stats=extraction_stats,
    )


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageResponse])
def get_messages(conv_id: str, db=Depends(get_db)):
    if not db.execute("SELECT 1 FROM conversations WHERE id = ?", (conv_id,)).fetchone():
        raise HTTPException(status_code=404, detail="대화 없음")
    rows = db.execute(
        "SELECT * FROM messages WHERE conversation_id = ? AND role != 'system' ORDER BY created_at",
        (conv_id,),
    ).fetchall()
    return [_row_to_msg(r) for r in rows]


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

    context_text, highlights = _restore_context(db, conv_id)
    history = _load_history(db, conv_id)
    history.append({"role": "user", "content": req.content})

    messages = build_chat_messages(context_text, history, highlights or None)
    llm_resp = client.complete(messages)
    assistant_text = llm_resp.text

    now = _now()
    asst_id = _persist_exchange(db, ChatExchange(
        conv_id=conv_id,
        user_content=req.content,
        assistant_text=assistant_text,
        now=now,
        had_title=bool(conv_row["title"]),
    ))

    pages = _json.loads(conv_row["pages_json"])
    conv_resp = ConversationResponse(
        id=conv_id, book_id=conv_row["book_id"], pdf_file_id=conv_row["pdf_file_id"],
        pages=pages, pages_display=format_pages(pages),
        title=req.content[:20].strip() if not conv_row["title"] else conv_row["title"],
        created_at=conv_row["created_at"],
    )
    msg_resp = MessageResponse(
        id=asst_id, conversation_id=conv_id, role="assistant",
        content=assistant_text, created_at=now,
    )
    return ChatResponse(conversation=conv_resp, message=msg_resp, usage=_build_usage_response(llm_resp.usage))
