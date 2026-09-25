"""OCR 캐시 BDD 명세."""
from __future__ import annotations

import sqlite3

import pytest

from app.db import init_db
from app.extractor import Block, BBox, ExtractionResult, PageExtraction
from app.ocr_cache import ExtractionTarget, get_or_extract


@pytest.fixture
def db(tmp_path, monkeypatch):
    """격리된 SQLite DB — init_db로 스키마 생성."""
    import app.db as db_mod
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db_mod, "_DB_PATH", db_path)
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


def _target(pdf_file_id, pages, pdf_path="test.pdf"):
    return ExtractionTarget(pdf_file_id=pdf_file_id, pages=pages, pdf_path=pdf_path)


class DescribeOcrCacheLayer:
    """get_or_extract 캐시 레이어의 동작 명세."""

    def test_cache_miss_calls_extractor_for_all_pages(self, db):
        # Given no cached pages
        calls: list[int] = []
        ext = _fake_extractor(calls)

        # When pages 1 and 2 are requested
        pages = get_or_extract(db, _target("pdf1", [1, 2]), ext)

        # Then the extractor was called for both pages and results are returned
        assert calls == [1, 2]
        assert len(pages) == 2
        assert pages[0].blocks[0].text == "page1"

    def test_cache_hit_skips_extractor(self, db):
        # Given page 1 is already cached
        calls: list[int] = []
        ext = _fake_extractor(calls)
        get_or_extract(db, _target("pdf1", [1]), ext)
        calls.clear()

        # When page 1 is requested again
        pages = get_or_extract(db, _target("pdf1", [1]), ext)

        # Then the extractor is not called and cached data is returned
        assert calls == []
        assert pages[0].blocks[0].text == "page1"

    def test_partial_cache_only_extracts_missing_pages(self, db):
        # Given page 1 is already cached
        calls: list[int] = []
        ext = _fake_extractor(calls)
        get_or_extract(db, _target("pdf1", [1]), ext)
        calls.clear()

        # When pages 1, 2, 3 are requested
        pages = get_or_extract(db, _target("pdf1", [1, 2, 3]), ext)

        # Then only pages 2 and 3 are extracted, and all 3 are returned
        assert set(calls) == {2, 3}
        assert len(pages) == 3

    def test_different_pdf_file_ids_are_isolated(self, db):
        """같은 page_num이라도 pdf_file_id가 다르면 별도 캐시를 사용한다."""
        # Given page 1 of pdf_A is cached
        calls: list[int] = []
        ext = _fake_extractor(calls)
        get_or_extract(db, _target("pdf_A", [1], "a.pdf"), ext)
        calls.clear()

        # When page 1 of a different pdf_B is requested
        get_or_extract(db, _target("pdf_B", [1], "b.pdf"), ext)

        # Then the extractor is called (pdf_B has no cache entry)
        assert calls == [1]
