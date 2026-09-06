"""LayoutExtractor 구현 모음 + 설정 기반 팩토리 (서버리스↔로컬↔fixture 스왑 지점)."""
from __future__ import annotations

from ..config import Settings, get_settings
from ..extractor import LayoutExtractor
from .base import ExtractionError
from .fixture_extractor import FixtureLayoutExtractor
from .modal_extractor import ModalLayoutExtractor

__all__ = [
    "ExtractionError",
    "ModalLayoutExtractor",
    "FixtureLayoutExtractor",
    "get_extractor",
]


def get_extractor(settings: Settings | None = None) -> LayoutExtractor:
    """EXTRACT_BACKEND 설정에 따라 LayoutExtractor 구현을 반환한다."""
    s = settings or get_settings()
    if s.extract_backend == "modal":
        return ModalLayoutExtractor.from_settings(s)
    if s.extract_backend == "fixture":
        return FixtureLayoutExtractor.from_settings(s)
    if s.extract_backend == "stub":
        from ..extractor import StubLayoutExtractor

        return StubLayoutExtractor()
    if s.extract_backend == "local":
        raise NotImplementedError("로컬 추출 구현은 장비 확보 후 (Sprint 1 범위 밖)")
    raise ValueError(f"unknown EXTRACT_BACKEND: {s.extract_backend}")
