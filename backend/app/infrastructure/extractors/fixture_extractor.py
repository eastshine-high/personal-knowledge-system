"""FixtureLayoutExtractor — 저장된 실제 엔드포인트 응답(fixture)을 재생하는 오프라인 구현.

Modal(서버리스 GPU) 없이 개발/데모/테스트를 $0로 돌리기 위한 구현. 페이지별 fixture
(`<fixtures_dir>/page{N}.json`, 실제 응답 캡처)를 읽어 BaseLayoutExtractor의 정규화/크롭 파이프라인에
그대로 흘려보낸다. 크롭은 실제 PDF를 로컬 렌더해 만들므로 figure image_ref도 정상 생성된다.
"""
from __future__ import annotations

import json
from pathlib import Path

from ...config import Settings, get_settings
from .base_extractor import BaseLayoutExtractor, ExtractionError

__all__ = ["FixtureLayoutExtractor"]


class FixtureLayoutExtractor(BaseLayoutExtractor):
    """`<fixtures_dir>/page{N}.json` 캡처 응답을 재생하는 오프라인 LayoutExtractor."""

    def __init__(
        self,
        fixtures_dir: str,
        *,
        render_dpi: int = 200,
        crop_dir: str = "backend/.crops",
    ) -> None:
        super().__init__(render_dpi=render_dpi, crop_dir=crop_dir)
        self._fixtures_dir = Path(fixtures_dir)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "FixtureLayoutExtractor":
        s = settings or get_settings()
        return cls(s.fixtures_dir, render_dpi=s.render_dpi, crop_dir=s.crop_dir)

    def _fetch_raw(self, page_no: int, img_bytes: bytes) -> dict:
        path = self._fixtures_dir / f"page{page_no}.json"
        if not path.is_file():
            raise ExtractionError(f"fixture 없음: {path} (page {page_no}). 캡처된 페이지만 재생 가능.")
        return json.loads(path.read_text(encoding="utf-8"))
