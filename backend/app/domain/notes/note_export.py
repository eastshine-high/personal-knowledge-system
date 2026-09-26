"""번들 내보내기 — 노트 마크다운 + 첨부 그림을 zip 하나로.

zip 내부는 평면 구조(노트 .md + 그림 파일이 같은 위치)라, 사용자가 옵시디언 vault로 옮기면
`![[embed_name]]`가 그대로 해석된다.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .note_models import Note


@dataclass
class ZipState:
    """zip 쓰기 중 추적 상태 — 파일명 중복·figure 이중 첨부 방지."""

    used_md: set[str] = field(default_factory=set)
    added_figs: set[str] = field(default_factory=set)


def _safe_filename(name: str, fallback: str) -> str:
    """파일명으로 안전하게 — 금지문자 치환, 빈 값이면 fallback."""
    slug = re.sub(r'[\\/:*?"<>|\n\r\t]', "_", name).strip().strip(".")
    return slug or fallback


def _unique_md_filename(title: str, note_id: str, used: set[str]) -> str:
    """충돌 없는 .md 파일명을 반환하고 used에 등록. 제목 중복 시 -2, -3 접미사."""
    base = _safe_filename(title, note_id)
    fname = f"{base}.md"
    dup = 2
    while fname in used:
        fname = f"{base}-{dup}.md"
        dup += 1
    used.add(fname)
    return fname


def _write_note_to_zip(zf: zipfile.ZipFile, note: Note, state: ZipState) -> None:
    """노트 마크다운과 미첨부 figure 크롭을 zf에 추가."""
    fname = _unique_md_filename(note.title, note.id, state.used_md)
    zf.writestr(fname, note.to_markdown())
    for fig in note.figures:
        if fig.embed_name in state.added_figs:
            continue
        src = Path(fig.source_path)
        if src.is_file():
            zf.write(src, fig.embed_name)
            state.added_figs.add(fig.embed_name)


def export_notes(notes: list[Note], out_zip_path: str) -> str:
    """노트[]와 첨부 그림을 zip으로 묶어 out_zip_path에 쓰고 경로를 반환."""
    if not notes:
        raise ValueError("내보낼 노트 없음")
    out = Path(out_zip_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    state = ZipState()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for note in notes:
            _write_note_to_zip(zf, note, state)
    return str(out)
