"""노트 조립 + 리파인 엔진 (Sprint 2)."""
from __future__ import annotations

from .models import Note, NoteDraft, NoteFigure, NoteKey, SessionEvent, make_note_id
from .export import export_notes
from .orchestrate import BuildSessionRequest, build_session
from .prepare import PreparedContext, PreparedFigure, prepare_context
from .session import EmptyTextError, NoteSession, SessionConfig
from .summarize import RefineRequest, SummarizeRequest, refine, summarize

__all__ = [
    "Note",
    "NoteDraft",
    "NoteFigure",
    "NoteKey",
    "SessionEvent",
    "make_note_id",
    "PreparedContext",
    "PreparedFigure",
    "prepare_context",
    "SummarizeRequest",
    "RefineRequest",
    "summarize",
    "refine",
    "NoteSession",
    "SessionConfig",
    "EmptyTextError",
    "BuildSessionRequest",
    "build_session",
    "export_notes",
]
