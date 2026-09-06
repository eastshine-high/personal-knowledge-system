"""번들 내보내기 — 노트 마크다운 + 첨부 그림을 zip 하나로.

zip 내부는 평면 구조(노트 .md + 그림 파일이 같은 위치)라, 사용자가 옵시디언 vault로 옮기면
`![[embed_name]]`가 그대로 해석된다.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

from .models import Note


def _safe_filename(name: str, fallback: str) -> str:
    """파일명으로 안전하게 — 금지문자 치환, 빈 값이면 fallback."""
    slug = re.sub(r'[\\/:*?"<>|\n\r\t]', "_", name).strip().strip(".")
    return slug or fallback


def export_notes(notes: list[Note], out_zip_path: str) -> str:
    """노트[]와 첨부 그림을 zip으로 묶어 out_zip_path에 쓰고 경로를 반환."""
    if not notes:
        raise ValueError("내보낼 노트 없음")

    out = Path(out_zip_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    used_md: set[str] = set()
    added_figs: set[str] = set()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for note in notes:
            base = _safe_filename(note.title, note.id)
            fname = f"{base}.md"
            dup = 2
            while fname in used_md:  # 제목 충돌 방지
                fname = f"{base}-{dup}.md"
                dup += 1
            used_md.add(fname)
            zf.writestr(fname, note.to_markdown())

            for fig in note.figures:
                if fig.embed_name in added_figs:
                    continue
                src = Path(fig.source_path)
                if src.is_file():        # 원본 크롭 파일이 있으면 번들에 복사
                    zf.write(src, fig.embed_name)
                    added_figs.add(fig.embed_name)
    return str(out)
