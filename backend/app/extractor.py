"""LayoutExtractor — PDF 페이지 범위에서 레이아웃 블록과 figure 크롭을 추출하는 교체가능 인터페이스.

Sprint 0: 인터페이스 시그니처만 확정한다. 실제 구현(PaddleOCR-VL, 서버리스 GPU→로컬)은 Sprint 1.
필드/라벨은 스파이크(docs/spike-paddleocr-vl.md)에서 **실측 확인**한 출력 형식에 맞춘다:
  - PP-StructureV3(mobile, on-device)와 PaddleOCR-VL(Modal A10G)이 동일한 parsing_res_list 구조를 냄.
  - 각 블록: block_label / block_bbox([x1,y1,x2,y2] 픽셀) / block_order(nullable) / block_content.

핵심 계약: 구현체는 엔드포인트(서버리스 GPU URL 또는 로컬)만 다르고 `extract()` 시그니처는 동일하다.
따라서 클라우드→로컬 전환이 구현체 교체(설정)만으로 끝난다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

# 정규화 블록 종류 — 프로젝트 도메인 어휘(CLAUDE.md)에 맞춘 표준 집합.
# 구현체는 PaddleOCR 원 라벨을 아래 RAW_LABEL_MAP으로 이 값에 매핑한다.
BlockType = Literal[
    "text",
    "title",
    "figure",
    "figure_caption",
    "table",
    "formula",
    "code",
    "header",
    "footer",
    "number",
    "other",
]

# PaddleOCR(PP-DocLayoutV3 / PP-StructureV3) 원 라벨 → 정규화 BlockType.
# docs/spike-paddleocr-vl.md 스파이크에서 실측 확인한 라벨 + 문서 taxonomy 반영.
# 미지 라벨은 normalize_label()이 "other"로 처리한다. Sprint 1에서 필요 시 확장.
RAW_LABEL_MAP: dict[str, BlockType] = {
    "text": "text",
    "title": "title",
    "doc_title": "title",
    "paragraph_title": "title",
    "image": "figure",          # ← VL/PP-Struct는 figure를 'image'로 냄
    "figure": "figure",
    "chart": "figure",
    "figure_title": "figure_caption",  # ← 그림 캡션은 'figure_title'
    "figure_caption": "figure_caption",
    "table": "table",
    "formula": "formula",
    "display_formula": "formula",       # ← VL은 수식을 'display_formula'로 냄
    "algorithm": "code",                # ← 코드 블록은 'algorithm'으로 냄
    "code": "code",
    "header": "header",
    "header_image": "header",
    "footer": "footer",
    "footer_image": "footer",
    "number": "number",                 # 페이지 번호
    "footnote": "other",
    "aside_text": "other",
    "seal": "other",
}


def normalize_label(raw_label: str) -> BlockType:
    """PaddleOCR 원 라벨을 정규화 BlockType으로. 미지 라벨은 'other'."""
    return RAW_LABEL_MAP.get(raw_label, "other")


@dataclass
class BBox:
    """바운딩박스 — 렌더된 페이지 이미지의 픽셀 좌표(좌상단 원점).

    좌표는 렌더 DPI에 종속된다(PageExtraction.render_dpi 참조). PDF 포인트가 아님.
    figure 크롭은 이 bbox로 렌더 페이지 이미지에서 crop 한다.
    """

    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class Block:
    """검출된 레이아웃 블록 하나."""

    type: BlockType
    bbox: BBox
    reading_order: int | None = None  # 비-흐름 블록(header/image/number 등)은 None
    text: str = ""                    # figure/image는 빈 문자열일 수 있음
    image_ref: str | None = None      # figure 크롭 이미지 경로/참조 (있으면)


@dataclass
class PageExtraction:
    page: int
    width_px: int = 0        # 렌더된 페이지 이미지 폭(px) — bbox 좌표계 기준
    height_px: int = 0       # 렌더된 페이지 이미지 높이(px)
    render_dpi: int = 200    # bbox 좌표를 만든 렌더 DPI (스파이크 기준 200)
    blocks: list[Block] = field(default_factory=list)


@dataclass
class ExtractionResult:
    source: str                    # 원본 PDF 파일명
    pages: list[PageExtraction] = field(default_factory=list)


@runtime_checkable
class LayoutExtractor(Protocol):
    """PDF + 페이지 범위 → 정규화된 레이아웃 추출 결과."""

    def extract(self, pdf_path: str, page_range: tuple[int, int]) -> ExtractionResult:
        ...


class StubLayoutExtractor:
    """Sprint 0 스텁 — 시그니처 검증용. 실제 추출은 Sprint 1 (PaddleOCR-VL)에서 구현."""

    def extract(self, pdf_path: str, page_range: tuple[int, int]) -> ExtractionResult:
        raise NotImplementedError("LayoutExtractor 구현은 Sprint 1 (PaddleOCR-VL)")
