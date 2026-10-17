"""detect_color_bands — 평탄화 형광색 밴드 검출 동작 명세."""
from __future__ import annotations

import pymupdf
import pytest

from app.infrastructure.extractors.highlight_color import detect_color_bands


def _page_with_rect(fill: tuple[float, float, float] | None):
    """(선택) 색칠 사각형 하나가 평탄화된 A4 페이지의 pixmap을 만든다."""
    doc = pymupdf.open()
    page = doc.new_page()  # 기본 A4 595x842
    if fill is not None:
        page.draw_rect(pymupdf.Rect(60, 120, 420, 150), fill=fill, color=fill)
    return page.get_pixmap(dpi=150)


class DescribeDetectColorBands:
    def test_detects_yellow_band(self):
        # Given a flattened yellow rectangle over a page
        pix = _page_with_rect((1, 1, 0))
        # When detecting color bands
        bands = detect_color_bands(pix)
        # Then exactly one yellow band is found near the top
        assert len(bands) == 1
        rect, color = bands[0]
        assert color == "yellow"
        assert rect.y0 < pix.height * 0.3  # 상단 영역

    def test_detects_green_band(self):
        # Given a flattened green rectangle
        pix = _page_with_rect((0, 1, 0))
        # When detecting
        bands = detect_color_bands(pix)
        # Then it is classified green
        assert len(bands) == 1
        assert bands[0][1] == "green"

    def test_blank_page_yields_no_bands(self):
        # Given a page with no highlight color
        pix = _page_with_rect(None)
        # Then no band is detected (오검출 0)
        assert detect_color_bands(pix) == []