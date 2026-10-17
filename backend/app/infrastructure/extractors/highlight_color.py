"""평탄화(픽셀) 형광펜 색 검출 — 렌더 pixmap에서 형광색 밴드의 bbox+색상을 찾는다.

GoodNotes 등은 형광펜을 PDF 주석이 아니라 페이지 이미지 픽셀로 평탄화한다(주석 0개).
여기서는 numpy로 색 마스킹 → 행 밴드 묶음 → 렌더 픽셀 Rect를 낸다.
반환 Rect는 base_extractor._blocks_in_rect로 OCR 블록과 교집합해 텍스트화한다.
"""
from __future__ import annotations

import numpy as np
import pymupdf

from ...domain.extractor import HighlightColor

# 밴드 판정 파라미터 — 행 최소 형광 픽셀 비율, 밴드 간 허용 간격, 최소 밴드 높이(px).
_MIN_ROW_RATIO = 0.02
_ROW_GAP_TOL = 6
_MIN_BAND_H = 3


def _pixmap_to_rgb(pix: "pymupdf.Pixmap") -> np.ndarray:
    """pixmap 샘플을 (H, W, 3) uint8 RGB 배열로. 알파 채널은 버린다."""
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    return arr[:, :, :3].astype(np.int16)


def _yellow_mask(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    """노란 형광 픽셀: R·G 높고 B 낮음(스파이크 실측 역치 기반)."""
    return (r > 180) & (g > 150) & (b < 160) & ((r + g - 2 * b) > 80)


def _green_mask(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    """초록 형광 픽셀: G가 R·B보다 뚜렷이 높음(노랑은 R도 높아 배제됨)."""
    return (g > 120) & ((g - r) > 30) & ((g - b) > 30)


def _bands_from_mask(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    """불리언 마스크에서 형광 밴드의 (x0, y0, x1, y1) 픽셀 사각형 목록."""
    w = mask.shape[1]
    row_hit = mask.sum(axis=1)
    hot = np.where(row_hit > max(5, w * _MIN_ROW_RATIO))[0]
    if len(hot) == 0:
        return []
    bands: list[tuple[int, int, int, int]] = []
    start = prev = int(hot[0])
    for y in hot[1:]:
        if int(y) - prev > _ROW_GAP_TOL:
            bands.append(_band_rect(mask, start, prev))
            start = int(y)
        prev = int(y)
    bands.append(_band_rect(mask, start, prev))
    return [b for b in bands if b[3] - b[1] >= _MIN_BAND_H]


def _band_rect(mask: np.ndarray, y0: int, y1: int) -> tuple[int, int, int, int]:
    """밴드 행 범위(y0..y1)에서 형광 픽셀이 걸친 좌우 범위를 더해 사각형을 만든다."""
    cols = np.where(mask[y0:y1 + 1].any(axis=0))[0]
    x0, x1 = (int(cols.min()), int(cols.max())) if len(cols) else (0, 0)
    return (x0, y0, x1, y1 + 1)


def detect_color_bands(pix: "pymupdf.Pixmap") -> list[tuple["pymupdf.Rect", HighlightColor]]:
    """렌더 pixmap에서 형광색 밴드를 찾아 (픽셀 Rect, 색상) 목록을 y 순으로 반환."""
    rgb = _pixmap_to_rgb(pix)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    found: list[tuple[pymupdf.Rect, HighlightColor]] = []
    for color, mask in (("yellow", _yellow_mask(r, g, b)), ("green", _green_mask(r, g, b))):
        for x0, y0, x1, y1 in _bands_from_mask(mask):
            found.append((pymupdf.Rect(x0, y0, x1, y1), color))  # type: ignore[arg-type]
    found.sort(key=lambda rc: rc[0].y0)
    return found