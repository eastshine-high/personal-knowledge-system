"""인메모리 노트 세션 스토어 — session_id → (NoteSession, pdf_path) 레지스트리."""
from __future__ import annotations

from ..domain.notes import NoteSession

# 인메모리 세션 스토어: session_id → (NoteSession, pdf_path)
_sessions: dict[str, tuple[NoteSession, str]] = {}


def get_session(session_id: str) -> tuple[NoteSession, str] | None:
    """session_id로 (NoteSession, pdf_path) 반환. 없으면 None."""
    return _sessions.get(session_id)


def put_session(session_id: str, session: NoteSession, pdf_path: str) -> None:
    """세션을 스토어에 등록한다."""
    _sessions[session_id] = (session, pdf_path)
