"""FastAPI 라우터 — 세션 생성·조회·리파인·내보내기 엔드포인트."""
from __future__ import annotations

import os
import tempfile
import uuid
from datetime import date
from pathlib import Path
from typing import Annotated

import pymupdf
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from fastapi.responses import FileResponse

from .config import get_settings
from .extractor import LayoutExtractor
from .extractors import get_extractor
from .extractors.base import ExtractionError
from .llm import LLMClient, get_llm_client
from .notes import EmptyTextError, NoteSession, build_session
from .notes.models import Note
from .notes.orchestrate import BuildSessionRequest
from .schemas import (
    CreateSessionRequest,
    EditRequest,
    EventResponse,
    FigureResponse,
    NoteResponse,
    RefineRequest,
    SessionResponse,
)

router = APIRouter()

# 인메모리 세션 스토어: session_id → (NoteSession, pdf_path)
_sessions: dict[str, tuple[NoteSession, str]] = {}


# --- 의존성 (테스트에서 dependency_overrides로 교체 가능) ------------------

def _extractor_dep() -> LayoutExtractor:
    return get_extractor(get_settings())


def _llm_dep() -> LLMClient:
    return get_llm_client(get_settings())


# --- 직렬화 헬퍼 -----------------------------------------------------------

def _note_to_resp(note: Note) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        title=note.title,
        source=note.source,
        pages=note.pages,
        topic=note.topic,
        created=note.created,
        body=note.body,
        tags=note.tags,
        figures=[FigureResponse(embed_name=f.embed_name, caption=f.caption) for f in note.figures],
        markdown=note.to_markdown(),
    )


def _session_resp(session_id: str, session: NoteSession) -> SessionResponse:
    return SessionResponse(
        session_id=session_id,
        notes=[_note_to_resp(n) for n in session.notes],
        events=[
            EventResponse(seq=e.seq, author=e.author, action=e.action, content=e.content)
            for e in session.events
        ],
    )


# --- 엔드포인트 ------------------------------------------------------------

@router.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(
    req: CreateSessionRequest,
    extractor: Annotated[LayoutExtractor, Depends(_extractor_dep)],
    client: Annotated[LLMClient, Depends(_llm_dep)],
) -> SessionResponse:
    """PDF + 범위 + 주제 → 노트 세션 생성. session_id로 이후 조작."""
    try:
        session = build_session(
            BuildSessionRequest(
                pdf_path=req.pdf_path,
                page_range=(req.page_start, req.page_end),
                topic=req.topic,
                guideline=req.guideline,
                note_count=req.note_count,
                created=date.today().isoformat(),
                user_preferred_guideline=req.user_preferred_guideline,
            ),
            extractor=extractor,
            client=client,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF 파일을 찾을 수 없음")
    except ExtractionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except EmptyTextError as e:
        raise HTTPException(status_code=422, detail=str(e))

    session_id = str(uuid.uuid4())
    _sessions[session_id] = (session, req.pdf_path)
    return _session_resp(session_id, session)


def _get_session(session_id: str) -> NoteSession:
    entry = _sessions.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="세션 없음")
    return entry[0]


@router.get("/sessions/{session_id}/notes", response_model=list[NoteResponse])
def get_notes(session_id: str) -> list[NoteResponse]:
    """현재 노트 목록 반환."""
    session = _get_session(session_id)
    return [_note_to_resp(n) for n in session.notes]


@router.post("/sessions/{session_id}/refine", response_model=SessionResponse)
def refine_session(session_id: str, req: RefineRequest) -> SessionResponse:
    """instruction으로 노트를 다듬는다."""
    session = _get_session(session_id)
    try:
        session.refine(req.instruction, note_id=req.note_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _session_resp(session_id, session)


@router.post("/sessions/{session_id}/notes/{note_id}/edit", response_model=NoteResponse)
def edit_note(session_id: str, note_id: str, req: EditRequest) -> NoteResponse:
    """노트를 직접 편집한다."""
    session = _get_session(session_id)
    try:
        note = session.apply_edit(note_id, req.body, title=req.title)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _note_to_resp(note)


@router.get("/sessions/{session_id}/pages/{page_num}")
def get_page_image(session_id: str, page_num: int) -> Response:
    """PDF 페이지를 PNG로 렌더링해서 반환한다."""
    _get_session(session_id)  # 404 체크
    pdf_path = _sessions[session_id][1]

    try:
        doc = pymupdf.open(pdf_path)
    except Exception:
        raise HTTPException(status_code=404, detail="PDF 파일을 열 수 없음")

    try:
        if page_num < 1 or page_num > doc.page_count:
            raise HTTPException(status_code=404, detail=f"페이지 {page_num} 없음 (총 {doc.page_count}페이지)")
        dpi = get_settings().render_dpi
        img_bytes = doc[page_num - 1].get_pixmap(dpi=dpi).tobytes("png")
    finally:
        doc.close()

    return Response(content=img_bytes, media_type="image/png")


@router.get("/sessions/{session_id}/export")
def export_session(session_id: str, background_tasks: BackgroundTasks) -> FileResponse:
    """현재 노트 + 첨부 그림을 zip으로 내보낸다."""
    session = _get_session(session_id)

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    try:
        session.export(tmp.name)
    except ValueError as e:
        os.unlink(tmp.name)
        raise HTTPException(status_code=422, detail=str(e))

    background_tasks.add_task(os.unlink, tmp.name)
    stem = Path(session.state["source"]).stem
    return FileResponse(tmp.name, media_type="application/zip", filename=f"{stem}-notes.zip")


@router.get("/sessions/{session_id}/figures/{filename}")
def get_figure(session_id: str, filename: str) -> FileResponse:
    """figure 크롭 이미지를 반환한다. embed_name으로 노트에서 source_path를 역조회."""
    session = _get_session(session_id)
    for note in session.notes:
        for fig in note.figures:
            if fig.embed_name == filename:
                src = Path(fig.source_path)
                if not src.is_file():
                    raise HTTPException(status_code=404, detail="크롭 파일 없음")
                return FileResponse(str(src), media_type="image/png")
    raise HTTPException(status_code=404, detail=f"그림 {filename} 없음")


@router.post("/sessions/{session_id}/undo", response_model=SessionResponse)
def undo_session(session_id: str) -> SessionResponse:
    """직전 변경을 되돌린다."""
    session = _get_session(session_id)
    try:
        session.undo()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _session_resp(session_id, session)
