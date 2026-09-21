"""T2 — OCR 캐시 단위 테스트."""
from __future__ import annotations

import sqlite3

import pytest

from app.db import init_db
from app.extractor import Block, BBox, ExtractionResult, PageExtraction
from app.ocr_cache import get_or_extract


@pytest.fixture
def db(tmp_path, monkeypatch):
    """인메모리가 아닌 tmp_path DB — init_db로 스키마 생성."""
    import app.db as db_mod
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db_mod, "_DB_PATH", db_path)
    # thread-local 초기화 리셋
    if hasattr(db_mod._local, "conn"):
        db_mod._local.conn.close()
        del db_mod._local.conn
    init_db()
    yield db_mod.get_db()
    db_mod._local.conn.close()
    del db_mod._local.conn


def _fake_extractor(call_log: list[int]):
    """호출된 page_num을 기록하는 stub extractor."""
    class _Ext:
        def extract(self, pdf_path, page_range):
            page_num = page_range[0]
            call_log.append(page_num)
            pe = PageExtraction(
                page=page_num, width_px=100, height_px=100, render_dpi=200,
                blocks=[Block(type="text", bbox=BBox(0, 0, 10, 10), text=f"page{page_num}")],
            )
            return ExtractionResult(source="test.pdf", pages=[pe])
    return _Ext()


def test_cache_miss_calls_extractor(db):
    calls: list[int] = []
    ext = _fake_extractor(calls)
    pages = get_or_extract(db, "pdf1", [1, 2], "test.pdf", ext)
    assert calls == [1, 2]
    assert len(pages) == 2
    assert pages[0].blocks[0].text == "page1"


def test_cache_hit_skips_extractor(db):
    calls: list[int] = []
    ext = _fake_extractor(calls)
    # 첫 번째 호출 — 캐시 저장
    get_or_extract(db, "pdf1", [1], "test.pdf", ext)
    calls.clear()
    # 두 번째 호출 — 캐시 히트, extractor 미호출
    pages = get_or_extract(db, "pdf1", [1], "test.pdf", ext)
    assert calls == []
    assert pages[0].blocks[0].text == "page1"


def test_partial_cache(db):
    calls: list[int] = []
    ext = _fake_extractor(calls)
    # 페이지 1 먼저 캐시
    get_or_extract(db, "pdf1", [1], "test.pdf", ext)
    calls.clear()
    # 페이지 1,2,3 요청 — 1은 캐시, 2,3만 추출
    pages = get_or_extract(db, "pdf1", [1, 2, 3], "test.pdf", ext)
    assert set(calls) == {2, 3}
    assert len(pages) == 3


def test_different_pdf_file_ids_isolated(db):
    """같은 page_num이라도 pdf_file_id가 다르면 별도 캐시."""
    calls: list[int] = []
    ext = _fake_extractor(calls)
    get_or_extract(db, "pdf_A", [1], "a.pdf", ext)
    calls.clear()
    get_or_extract(db, "pdf_B", [1], "b.pdf", ext)
    assert calls == [1]  # pdf_B는 캐시 없음
