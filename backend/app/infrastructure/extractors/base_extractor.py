"""BaseLayoutExtractor — 렌더 루프 + 정규화 + figure 크롭 공유 로직.

구현체(Modal/Fixture)는 "raw parsing 응답을 어디서 가져오는지"(`_fetch_raw`)만 다르다.
raw 응답 형식: {"meta": {"width","height","labels"}, "blocks": [{"order","id","label","bbox","content"}], ...}
"""
from __future__ import annotations

from pathlib import Path

import pymupdf

from ...domain.extractor import (
    BBox,
    Block,
    ExtractionResult,
    PageExtraction,
    normalize_label,
)


def _dedup_ordered(items: list[str]) -> list[str]:
    """순서를 유지하며 중복을 제거한 새 리스트 반환."""
    seen: set[str] = set()
    out: list[str] = []
    for t in items:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


class ExtractionError(RuntimeError):
    """추출 파이프라인 실패 (렌더/응답 획득/파싱)."""


class BaseLayoutExtractor:
    """PDF 페이지 범위 → 렌더 → raw 획득(_fetch_raw) → 정규화/크롭 → ExtractionResult."""

    def __init__(self, *, render_dpi: int = 200, crop_dir: str = "backend/.crops") -> None:
        self._dpi = render_dpi
        self._crop_dir = crop_dir

    def extract(self, pdf_path: str, page_range: tuple[int, int]) -> ExtractionResult:
        start, end = page_range
        if start < 1 or end < start:
            raise ValueError(f"invalid page_range: {page_range}")

        self._before_extract()

        doc = pymupdf.open(pdf_path)
        try:
            result = ExtractionResult(source=Path(pdf_path).name)
            for page_no in range(start, end + 1):
                if page_no > doc.page_count:
                    break
                page = doc[page_no - 1]  # page_range는 1-based, pymupdf는 0-based
                img_bytes = page.get_pixmap(dpi=self._dpi).tobytes("png")
                raw = self._fetch_raw(page_no, img_bytes)
                result.pages.append(self._assemble_page(page_no, raw, page))
            return result
        finally:
            doc.close()

    # --- 구현체가 채우는 훅 ---------------------------------------------
    def _before_extract(self) -> None:
        """추출 시작 전 1회 호출(예: 워밍업). 기본 no-op."""

    def _fetch_raw(self, page_no: int, img_bytes: bytes) -> dict:
        """페이지의 raw parsing 응답을 반환. 구현체가 정의."""
        raise NotImplementedError

    # --- 공유 로직 -----------------------------------------------------
    def _assemble_page(self, page_no: int, raw: dict, page: "pymupdf.Page") -> PageExtraction:
        """raw 응답을 PageExtraction으로 조립 — 블록 파싱 + 형광 추출."""
        meta = raw.get("meta") or {}
        pe = PageExtraction(
            page=page_no,
            width_px=int(meta.get("width") or 0),
            height_px=int(meta.get("height") or 0),
            render_dpi=self._dpi,
        )
        for rb in raw.get("blocks") or []:
            pe.blocks.append(self._make_block(rb, page, page_no))
        pe.highlights = self._extract_highlights(page, pe.blocks)
        return pe

    def _make_block(self, rb: dict, page: "pymupdf.Page", page_no: int) -> Block:
        """raw 블록 딕셔너리를 Block으로 변환. figure면 crop 시도."""
        bbox_vals = rb.get("bbox") or [0, 0, 0, 0]
        bbox = BBox(*[float(v) for v in bbox_vals])
        block_type = normalize_label(rb.get("label", ""))
        image_ref = self._crop_figure(page, page_no, bbox) if block_type == "figure" else None
        return Block(
            type=block_type,
            bbox=bbox,
            reading_order=rb.get("order"),
            text=rb.get("content", "") or "",
            image_ref=image_ref,
        )

    def _extract_highlights(self, page: "pymupdf.Page", blocks: "list[Block]") -> "list[str]":
        """PDF 형광 표시(highlight) 주석에서 텍스트를 수집한다.

        1차: 페이지 텍스트 레이어에서 추출 (대부분의 GoodNotes PDF)
        폴백: annotation rect를 render 픽셀로 변환해 OCR 블록과 매핑 (스캔 전용 PDF)
        """
        results: list[str] = []
        for annot in page.annots() or []:
            if annot.type[0] != pymupdf.PDF_ANNOT_HIGHLIGHT:
                continue
            text = page.get_textbox(annot.rect).strip()
            if not text:
                sx = self._dpi / 72.0
                r = annot.rect
                px_rect = pymupdf.Rect(r.x0 * sx, r.y0 * sx, r.x1 * sx, r.y1 * sx)
                text = self._blocks_in_rect(px_rect, blocks)
            if text:
                results.append(text)
        return _dedup_ordered(results)

    def _blocks_in_rect(self, rect: "pymupdf.Rect", blocks: "list[Block]") -> str:
        """annotation bbox(render 픽셀)와 50% 이상 겹치는 텍스트 블록을 이어붙여 반환."""
        texts: list[str] = []
        for b in blocks:
            if not b.text:
                continue
            bx = pymupdf.Rect(b.bbox.x0, b.bbox.y0, b.bbox.x1, b.bbox.y1)
            inter = bx & rect
            if inter.is_empty:
                continue
            block_area = bx.get_area()
            if block_area > 0 and inter.get_area() / block_area >= 0.5:
                texts.append(b.text.strip())
        return " ".join(texts)

    def _crop_figure(self, page: "pymupdf.Page", page_no: int, bbox: BBox) -> str | None:
        """figure 영역을 페이지에서 clip-render(픽셀→포인트)해 crop_dir에 저장, 파일 경로 반환."""
        f = 72.0 / self._dpi  # 렌더 픽셀 → PDF 포인트
        rect = pymupdf.Rect(bbox.x0 * f, bbox.y0 * f, bbox.x1 * f, bbox.y1 * f)
        if rect.is_empty:
            return None
        try:
            crop = page.get_pixmap(dpi=self._dpi, clip=rect)
            out_dir = Path(self._crop_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"p{page_no}_{round(bbox.x0)}_{round(bbox.y0)}_{round(bbox.x1)}_{round(bbox.y1)}.png"
            crop.save(str(path))
            return str(path)
        except Exception:
            return None  # 크롭 실패는 추출 전체를 깨뜨리지 않는다
