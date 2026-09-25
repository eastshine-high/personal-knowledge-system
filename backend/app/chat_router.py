"""자유 대화 API — 대화 생성·조회·메시지 전송."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from .config import get_settings
from .db import get_db
from .extractor import LayoutExtractor
from .extractors import get_extractor
from .llm import LLMClient, get_llm_client
from .llm.chat_prompt import build_chat_messages
from .notes.prepare import PreparedContext, prepare_context
from .ocr_cache import get_or_extract
from .pages import format_pages, parse_pages
from .schemas import (
    ChatResponse,
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
)

router = APIRouter(tags=["chat"])


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _extractor_dep() -> LayoutExtractor:
    return get_extractor(get_settings())


def _llm_dep() -> LLMClient:
    return get_llm_client(get_settings())


def _row_to_conv(row) -> ConversationResponse:
    import json
    pages = json.loads(row["pages_json"])
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
):
    import json as _json

    if not db.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone():
        raise HTTPException(status_code=404, detail="책 없음")

    pdf_row = db.execute(
        "SELECT * FROM pdf_files WHERE id = ? AND book_id = ?",
        (req.pdf_file_id, book_id),
    ).fetchone()
    if not pdf_row:
        raise HTTPException(status_code=404, detail="PDF 파일 없음")

    try:
        pages = parse_pages(req.pages_str)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # OCR 캐시 경유 추출 (텍스트 컨텍스트 준비)
    page_extractions = get_or_extract(
        db, req.pdf_file_id, pages, pdf_row["pdf_path"], extractor
    )

    # ExtractionResult 조립 → PreparedContext
    from .extractor import ExtractionResult
    result = ExtractionResult(source=pdf_row["pdf_path"], pages=page_extractions)
    context: PreparedContext = prepare_context(result)

    # 대화 저장 (context_text는 messages 전송 시 재구성)
    conv_id = str(uuid.uuid4())
    now = _now()
    db.execute(
        "INSERT INTO conversations (id, book_id, pdf_file_id, pages_json, title, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (conv_id, book_id, req.pdf_file_id, _json.dumps(pages), None, now),
    )
    # highlights 수집 — use_highlights=True일 때만 (기본 off)
    all_highlights: list[str] = []
    if req.use_highlights:
        _seen_h: set[str] = set()
        for pe in page_extractions:
            for h in pe.highlights:
                if h not in _seen_h:
                    _seen_h.add(h)
                    all_highlights.append(h)

    # context_text (+ highlights) 를 system 메시지로 저장해 이후 대화에서 재사용
    sys_content = context.text
    if all_highlights:
        sys_content += "\n\n[HIGHLIGHTS_JSON]" + _json.dumps(all_highlights, ensure_ascii=False)
    sys_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?,?,?,?,?)",
        (sys_id, conv_id, "system", sys_content, now),
    )
    db.commit()

    return ConversationResponse(
        id=conv_id,
        book_id=book_id,
        pdf_file_id=req.pdf_file_id,
        pages=pages,
        pages_display=format_pages(pages),
        title=None,
        created_at=now,
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

    # context_text 복원 (system 메시지)
    sys_row = db.execute(
        "SELECT content FROM messages WHERE conversation_id = ? AND role = 'system' LIMIT 1",
        (conv_id,),
    ).fetchone()
    raw_sys = sys_row["content"] if sys_row else ""
    _HMARKER = "\n\n[HIGHLIGHTS_JSON]"
    if _HMARKER in raw_sys:
        _parts = raw_sys.split(_HMARKER, 1)
        context_text = _parts[0]
        try:
            import json as _json2
            highlights: list[str] = _json2.loads(_parts[1])
        except (ValueError, IndexError):
            highlights = []
    else:
        context_text = raw_sys
        highlights = []

    # 기존 user/assistant 히스토리
    history_rows = db.execute(
        "SELECT role, content FROM messages "
        "WHERE conversation_id = ? AND role != 'system' ORDER BY created_at",
        (conv_id,),
    ).fetchall()
    history = [{"role": r["role"], "content": r["content"]} for r in history_rows]
    history.append({"role": "user", "content": req.content})

    messages = build_chat_messages(context_text, history, highlights or None)
    assistant_text = client.complete(messages)

    now = _now()
    user_id = str(uuid.uuid4())
    asst_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?,?,?,?,?)",
        (user_id, conv_id, "user", req.content, now),
    )
    db.execute(
        "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?,?,?,?,?)",
        (asst_id, conv_id, "assistant", assistant_text, now),
    )
    # 첫 메시지로 대화 제목 자동 설정
    if not conv_row["title"]:
        title = req.content[:20].strip()
        db.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id))
    db.commit()

    import json as _json
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
    return ChatResponse(conversation=conv_resp, message=msg_resp)
