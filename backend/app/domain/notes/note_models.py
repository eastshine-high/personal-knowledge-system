"""노트 모델 — 프론트매터가 붙은 요약 노트, LLM 초안, 첨부 그림.

프론트매터 스키마(spec 확정): id / title / source / pages / topic / tags / created.
`id`·`created`는 주입식(결정적) — 테스트 재현성을 위해 외부에서 넣는다.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class NoteKey:
    """노트 ID 생성에 쓰이는 식별 키 — source + pages + topic + (index)."""

    source: str
    pages: list[int]
    topic: str
    index: int = 0


def make_note_id(key: NoteKey) -> str:
    """NoteKey로 안정적·결정적 노트 ID를 만든다."""
    raw = f"{key.source}|{','.join(str(p) for p in key.pages)}|{key.topic}|{key.index}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _yaml_str(s: str) -> str:
    """YAML 스칼라를 안전하게 큰따옴표로 감싸고 이스케이프."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


@dataclass
class NoteFigure:
    """노트에 첨부되는 그림 — 번들 내 파일명 + 원본 크롭 경로(export 복사원) + 캡션."""

    embed_name: str      # 번들/노트에서 참조하는 파일명 (예: Building-AI-Agent-p200-fig1.png)
    source_path: str     # 원본 figure 크롭 경로 (export 시 복사원)
    caption: str = ""


@dataclass
class NoteDraft:
    """LLM(Summarizer)이 내는 초안 — 제목 + 본문(마크다운). 프론트매터는 엔진이 조립."""

    title: str
    body: str


@dataclass
class SessionEvent:
    """ADK식 세션 이벤트 — append-only 이력의 한 항목.

    `state_delta`는 이 이벤트로 적용된 변경분(우리 v1은 `notes` 스냅샷 포함)이라, 이벤트를 되짚어
    특정 시점 상태를 복원(undo/revert)할 수 있다.
    """

    seq: int
    author: str          # "user" | "agent" | "system"
    action: str          # "start" | "refine" | "apply_edit" | "revert"
    content: str         # 지시문 또는 설명
    state_delta: dict     # 이 시점의 변경분 (notes 스냅샷 등)


def _build_frontmatter(note: "Note") -> list[str]:
    """옵시디언 YAML 프론트매터 줄 목록 반환 (--- 구분자 포함)."""
    pages = "[" + ", ".join(str(p) for p in note.pages) + "]"
    tags = "[" + ", ".join(_yaml_str(t) for t in note.tags) + "]"
    return [
        "---",
        f"id: {note.id}",
        f"title: {_yaml_str(note.title)}",
        f"source: {_yaml_str(note.source)}",
        f"pages: {pages}",
        f"topic: {_yaml_str(note.topic)}",
        f"tags: {tags}",
        f"created: {note.created}",
        "---",
    ]


@dataclass
class Note:
    """프론트매터 + 본문 + 첨부 그림을 가진 요약 노트."""

    id: str
    title: str
    source: str
    pages: list[int]
    topic: str
    created: str                 # ISO 날짜 "YYYY-MM-DD" (주입식)
    body: str = ""
    tags: list[str] = field(default_factory=list)
    figures: list[NoteFigure] = field(default_factory=list)

    def to_markdown(self) -> str:
        """프론트매터 + 본문 + 그림 섹션을 옵시디언 호환 마크다운으로 렌더.

        그림 임베드(![[..]])는 body가 아니라 `self.figures`(1급 상태)에서 렌더한다.
        → refine/직접편집이 body만 바꿔도 그림 참조가 항상 유지된다.
        """
        parts = _build_frontmatter(self) + ["", self.body.rstrip()]
        if self.figures:
            embeds = "\n".join(
                f"![[{f.embed_name}]]" + (f"\n*{f.caption}*" if f.caption else "")
                for f in self.figures
            )
            parts += ["", "## 그림", embeds]
        return "\n".join(parts) + "\n"
