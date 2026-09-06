"""NoteSession — 노트 조립 + 리파인의 상태를 가진 세션.

start(): 준비된 컨텍스트(텍스트+그림) → LLM 요약 → 완성 노트[](프론트매터+본문+![[그림]]).
refine()/apply_edit()로 대화형으로 다듬는다. 직접 편집분이 다음 refine의 기준.
"""
from __future__ import annotations

from pathlib import Path

from ..llm import LLMClient
from .models import Note, NoteFigure, make_note_id
from .prepare import PreparedContext
from .summarize import refine as _refine_draft
from .summarize import summarize


class EmptyTextError(ValueError):
    """요약할 텍스트가 없음 (빈 노트 생성 방지)."""


class NoteSession:
    def __init__(
        self,
        *,
        client: LLMClient,
        context: PreparedContext,
        source: str,
        pages: list[int],
        topic: str,
        guideline: str | None = None,
        created: str,
    ) -> None:
        self.client = client
        self.context = context
        self.source = source
        self.pages = pages
        self.topic = topic
        self.guideline = guideline
        self.created = created
        self.notes: list[Note] = []
        self.history: list[dict] = []

    def start(self, note_count: int = 1) -> list[Note]:
        """추출 텍스트를 요약해 초기 노트[]를 만든다. 그림은 (v1) 첫 노트에 첨부."""
        if not self.context.text.strip():
            raise EmptyTextError("요약할 텍스트 없음")
        drafts = summarize(
            self.client,
            self.context.text,
            topic=self.topic,
            guideline=self.guideline,
            note_count=note_count,
        )
        self.notes = [
            self._assemble_note(i, draft, attach_figures=(i == 0))
            for i, draft in enumerate(drafts)
        ]
        self.history = [{"action": "start", "note_count": note_count}]
        return self.notes

    def refine(self, instruction: str, *, note_id: str | None = None) -> list[Note]:
        """현재 노트를 후속 지시로 다듬는다.

        프론트매터/그림은 유지, title/body만 갱신. 실패 시 상태 무손상(전체 계산 후 일괄 적용).
        """
        targets = self.notes if note_id is None else [n for n in self.notes if n.id == note_id]
        if not targets:
            raise ValueError(f"note_id 없음: {note_id}")
        drafts = [
            (note, _refine_draft(
                self.client, f"TITLE: {note.title}\n\n{note.body}", instruction, text=self.context.text,
            ))
            for note in targets
        ]
        for note, draft in drafts:  # 전부 성공했을 때만 적용
            note.title = draft.title
            note.body = draft.body
        self.history.append({"action": "refine", "instruction": instruction, "note_id": note_id})
        return targets

    def apply_edit(self, note_id: str, body: str, *, title: str | None = None) -> Note:
        """사용자의 직접 편집을 노트의 현재 상태로 반영(다음 refine의 기준)."""
        note = next((n for n in self.notes if n.id == note_id), None)
        if note is None:
            raise ValueError(f"note_id 없음: {note_id}")
        note.body = body
        if title is not None:
            note.title = title
        self.history.append({"action": "apply_edit", "note_id": note_id})
        return note

    def export(self, out_zip_path: str) -> str:
        """현재 노트[]와 첨부 그림을 zip 번들로 내보낸다."""
        from .export import export_notes

        return export_notes(self.notes, out_zip_path)

    # --- 조립 ----------------------------------------------------------
    def _assemble_note(self, index: int, draft, attach_figures: bool) -> Note:
        # 그림 임베드는 body에 넣지 않는다 — to_markdown()이 figures에서 렌더(refine/편집에도 유지).
        return Note(
            id=make_note_id(self.source, self.pages, self.topic, index),
            title=draft.title,
            source=self.source,
            pages=self.pages,
            topic=self.topic,
            created=self.created,
            body=draft.body,
            tags=[],
            figures=self._build_note_figures() if attach_figures else [],
        )

    def _build_note_figures(self) -> list[NoteFigure]:
        """준비된 그림을 옵시디언 친화 파일명({source}-p{page}-fig{n}.png)으로 변환."""
        stem = Path(self.source).stem
        per_page: dict[int, int] = {}
        out: list[NoteFigure] = []
        for fig in self.context.figures:
            if not fig.source_path:  # 크롭 실패한 그림은 첨부하지 않음
                continue
            per_page[fig.page] = per_page.get(fig.page, 0) + 1
            embed = f"{stem}-p{fig.page}-fig{per_page[fig.page]}.png"
            out.append(
                NoteFigure(embed_name=embed, source_path=fig.source_path, caption=fig.caption)
            )
        return out
