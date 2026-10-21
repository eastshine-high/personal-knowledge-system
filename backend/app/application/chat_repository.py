"""자유 대화 DB 쿼리 — 대화·메시지 조회/저장 (FastAPI import 없음)."""
from __future__ import annotations

import json as _json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from ..pages import format_pages
from ..schemas import ConversationResponse, MessageResponse


def now() -> str:
    """현재 UTC 시각 ISO 문자열 반환."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


@dataclass
class ChatExchange:
    """persist_exchange 호출 파라미터 — 대화 ID·user/assistant 메시지·타임스탬프·제목/주제 유무."""

    conv_id: str
    user_content: str
    assistant_text: str
    now: str
    had_title: bool
    had_topic: bool = False


def row_to_conv(row) -> ConversationResponse:
    """DB 행을 ConversationResponse로 변환."""
    pages = _json.loads(row["pages_json"])
    return ConversationResponse(
        id=row["id"],
        book_id=row["book_id"],
        pdf_file_id=row["pdf_file_id"],
        pages=pages,
        pages_display=format_pages(pages),
        title=row["title"],
        topic=row["topic"],
        created_at=row["created_at"],
    )


def row_to_msg(row) -> MessageResponse:
    """DB 행을 MessageResponse로 변환."""
    return MessageResponse(
        id=row["id"],
        conversation_id=row["conversation_id"],
        role=row["role"],
        content=row["content"],
        created_at=row["created_at"],
    )


def resolve_pdf_row(db, book_id: str, pdf_file_id: str):
    """book + pdf 존재 검증 후 pdf_row 반환. 없으면 None 또는 False 반환."""
    if not db.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone():
        return None, "책"
    row = db.execute(
        "SELECT * FROM pdf_files WHERE id = ? AND book_id = ?",
        (pdf_file_id, book_id),
    ).fetchone()
    if not row:
        return None, "PDF"
    return row, None


def restore_context(db, conv_id: str) -> tuple[str, list[str]]:
    """system 메시지에서 context_text와 highlights를 복원."""
    _HMARKER = "\n\n[HIGHLIGHTS_JSON]"
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


def load_history(db, conv_id: str) -> list[dict]:
    """대화의 user/assistant 메시지 이력을 시간순으로 반환."""
    rows = db.execute(
        "SELECT role, content FROM messages "
        "WHERE conversation_id = ? AND role != 'system' ORDER BY created_at",
        (conv_id,),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def persist_exchange(db, exchange: ChatExchange) -> str:
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
    first_line = exchange.user_content[:20].strip()
    if not exchange.had_title:
        db.execute("UPDATE conversations SET title = ? WHERE id = ?", (first_line, exchange.conv_id))
    if not exchange.had_topic:
        db.execute("UPDATE conversations SET topic = ? WHERE id = ?", (first_line, exchange.conv_id))
    db.commit()
    return asst_id
