"""NoteSession — ADK Session 개념(state + events)을 차용한 노트 조립·리파인 세션.

- `state`: 현재 작업 메모리(KV). prefix 규칙 — `user:`(세션 간), `temp:`(이번 턴만·미영속), 무prefix(세션).
- `events`: append-only 이력. 모든 변경은 이벤트로 기록(`state_delta`에 notes 스냅샷) → 감사·undo 가능.
- 상태는 직접 필드가 아니라 `state`를 경유하며, 변경은 항상 `_record_event`를 통한다.
- refine은 최근 지시(events)를 LLM 프롬프트 맥락으로 주입(다중턴). guideline 미지정 시 `user:preferred_guideline` 폴백.

docs/adk-context-notes.md 참조.
"""
from __future__ import annotations

import copy
from pathlib import Path

from ..llm import LLMClient
from .models import Note, NoteFigure, SessionEvent, make_note_id
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
        user_preferred_guideline: str | None = None,
    ) -> None:
        self.client = client
        self.state: dict = {
            "source_text": context.text,
            "figures": context.figures,
            "source": source,
            "pages": pages,
            "topic": topic,
            "guideline": guideline,
            "created": created,
            "notes": [],
        }
        if user_preferred_guideline is not None:
            self.state["user:preferred_guideline"] = user_preferred_guideline
        self.events: list[SessionEvent] = []

    @property
    def notes(self) -> list[Note]:
        return self.state["notes"]

    # --- 액션 (모두 이벤트 경유) ---------------------------------------
    def start(self, note_count: int = 1) -> list[Note]:
        """추출 텍스트를 요약해 초기 노트[]를 만든다. 그림은 (v1) 첫 노트에 첨부."""
        text = self.state["source_text"]
        if not text.strip():
            raise EmptyTextError("요약할 텍스트 없음")
        # guideline 미지정 시 사용자 취향(user: 스코프) 폴백
        guideline = self.state.get("guideline") or self.state.get("user:preferred_guideline")
        drafts = summarize(
            self.client, text, topic=self.state["topic"], guideline=guideline, note_count=note_count
        )
        self.state["notes"] = [
            self._assemble_note(i, draft, attach_figures=(i == 0))
            for i, draft in enumerate(drafts)
        ]
        self._record_event("start", "agent", f"note_count={note_count}")
        return self.notes

    def refine(self, instruction: str, *, note_id: str | None = None) -> list[Note]:
        """현재 노트를 후속 지시로 다듬는다. 최근 지시(events)를 맥락으로 함께 전달(다중턴).

        프론트매터/그림은 유지, title/body만 갱신. 실패 시 상태 무손상(전체 계산 후 일괄 적용).
        """
        notes = self.state["notes"]
        targets = notes if note_id is None else [n for n in notes if n.id == note_id]
        if not targets:
            raise ValueError(f"note_id 없음: {note_id}")
        prior = self._recent_instructions()
        drafts = [
            (note, _refine_draft(
                self.client, f"TITLE: {note.title}\n\n{note.body}", instruction,
                text=self.state["source_text"], history=prior,
            ))
            for note in targets
        ]
        for note, draft in drafts:  # 전부 성공했을 때만 적용
            note.title = draft.title
            note.body = draft.body
        self._record_event("refine", "user", instruction)
        return targets

    def apply_edit(self, note_id: str, body: str, *, title: str | None = None) -> Note:
        """사용자의 직접 편집을 노트의 현재 상태로 반영(다음 refine의 기준)."""
        note = next((n for n in self.state["notes"] if n.id == note_id), None)
        if note is None:
            raise ValueError(f"note_id 없음: {note_id}")
        note.body = body
        if title is not None:
            note.title = title
        self._record_event("apply_edit", "user", "직접 편집")
        return note

    def export(self, out_zip_path: str) -> str:
        """현재 노트[]와 첨부 그림을 zip 번들로 내보낸다."""
        from .export import export_notes

        return export_notes(self.notes, out_zip_path)

    # --- undo / 이력 복원 (event replay) --------------------------------
    def revert_to(self, seq: int) -> list[Note]:
        """seq번째 이벤트 시점의 노트 상태로 되돌린다(append-only: revert 이벤트를 추가)."""
        if not (0 <= seq < len(self.events)):
            raise ValueError(f"잘못된 seq: {seq}")
        self.state["notes"] = copy.deepcopy(self.events[seq].state_delta["notes"])
        self._record_event("revert", "user", f"seq {seq}로 복원")
        return self.notes

    def undo(self) -> list[Note]:
        """직전 변경을 되돌린다(바로 이전 이벤트 상태로)."""
        if len(self.events) < 2:
            raise ValueError("되돌릴 이전 상태가 없음")
        return self.revert_to(len(self.events) - 2)

    # --- 내부 ----------------------------------------------------------
    def _record_event(self, action: str, author: str, content: str, extra_delta: dict | None = None) -> None:
        # state["notes"]는 이미 in-place 갱신됨. 이벤트엔 불변 스냅샷(deepcopy) 기록 → undo용.
        delta: dict = {"notes": copy.deepcopy(self.state["notes"])}
        if extra_delta:
            for key, value in extra_delta.items():
                delta[key] = value
                if not key.startswith("temp:"):   # temp: 는 영속 state에 남기지 않음
                    self.state[key] = value
        self.events.append(
            SessionEvent(seq=len(self.events), author=author, action=action, content=content, state_delta=delta)
        )

    def _recent_instructions(self, limit: int = 5) -> list[str]:
        """LLM 맥락으로 넘길 최근 refine 지시들(오래된→최신)."""
        return [e.content for e in self.events if e.action == "refine"][-limit:]

    def _assemble_note(self, index: int, draft, attach_figures: bool) -> Note:
        # 그림 임베드는 body가 아니라 to_markdown()이 figures에서 렌더(refine/편집에도 유지).
        return Note(
            id=make_note_id(self.state["source"], self.state["pages"], self.state["topic"], index),
            title=draft.title,
            source=self.state["source"],
            pages=self.state["pages"],
            topic=self.state["topic"],
            created=self.state["created"],
            body=draft.body,
            tags=[],
            figures=self._build_note_figures() if attach_figures else [],
        )

    def _build_note_figures(self) -> list[NoteFigure]:
        """준비된 그림을 옵시디언 친화 파일명({source}-p{page}-fig{n}.png)으로 변환."""
        stem = Path(self.state["source"]).stem
        per_page: dict[int, int] = {}
        out: list[NoteFigure] = []
        for fig in self.state["figures"]:
            if not fig.source_path:  # 크롭 실패한 그림은 첨부하지 않음
                continue
            per_page[fig.page] = per_page.get(fig.page, 0) + 1
            embed = f"{stem}-p{fig.page}-fig{per_page[fig.page]}.png"
            out.append(
                NoteFigure(embed_name=embed, source_path=fig.source_path, caption=fig.caption)
            )
        return out
