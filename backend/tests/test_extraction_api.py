"""추출 세트 API BDD 명세 — 주제별 OCR 범위 + 대화와의 캐시 공유/독립성."""
from __future__ import annotations

import sqlite3

import app.db as db_mod
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.domain.extractor import BBox, Block, ExtractionResult, PageExtraction
from app.infrastructure import get_llm_client


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    db_mod._DB_PATH = tmp_path / "test.db"
    if hasattr(db_mod._local, "conn"):
        db_mod._local.conn.close()
        del db_mod._local.conn
    yield
    if hasattr(db_mod._local, "conn"):
        db_mod._local.conn.close()
        del db_mod._local.conn


class _CountingExtractor:
    """extract() 호출(페이지 범위)을 기록 — 캐시 재사용 검증용."""
    def __init__(self):
        self.calls: list[tuple[int, int]] = []

    def extract(self, pdf_path, page_range):
        self.calls.append(page_range)
        p = page_range[0]
        pe = PageExtraction(
            page=p, width_px=100, height_px=100, render_dpi=200,
            blocks=[Block(type="text", bbox=BBox(0, 0, 10, 10), text=f"page{p}")],
        )
        return ExtractionResult(source=pdf_path, pages=[pe])


@pytest.fixture
def ctx(tmp_path):
    """book + pdf가 등록되고, 추출/대화 라우터가 같은 추출기를 공유하는 상태."""
    from app.main import app
    from app.presentation import chat_router, extraction_router
    stub = _CountingExtractor()
    app.dependency_overrides[extraction_router._extractor_dep] = lambda: stub
    app.dependency_overrides[chat_router._extractor_dep] = lambda: stub
    app.dependency_overrides[chat_router._llm_dep] = lambda: get_llm_client(
        get_settings().__class__(**{**get_settings().__dict__, "llm_backend": "mock"})
    )
    with TestClient(app) as c:
        book = c.post("/books", json={"title": "b"}).json()
        pdf = tmp_path / "t.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        pf = c.post(f"/books/{book['id']}/pdfs", json={"label": "c", "pdf_path": str(pdf)}).json()
        yield c, stub, book, pf
    app.dependency_overrides.clear()


def _count_cached_pages(pdf_id: str) -> int:
    conn = sqlite3.connect(db_mod._DB_PATH)
    n = conn.execute(
        "SELECT COUNT(*) FROM page_extractions WHERE pdf_file_id=?", (pdf_id,)
    ).fetchone()[0]
    conn.close()
    return n


class DescribeCreateExtraction:
    def test_creates_set_and_caches_its_pages(self, ctx):
        # Given a book+pdf
        c, _, book, pf = ctx
        # When an extraction set over "1-5" is created
        r = c.post(f"/books/{book['id']}/pdfs/{pf['id']}/extractions",
                   json={"topic": "자료구조", "pages_str": "1-5"})
        # Then it is created and pages 1-5 are OCR-cached
        assert r.status_code == 201
        ext = r.json()
        assert ext["topic"] == "자료구조"
        assert ext["pages"] == [1, 2, 3, 4, 5]
        assert _count_cached_pages(pf["id"]) == 5

    def test_conversation_reuses_extraction_cache(self, ctx):
        # Given an extraction set OCR'd pages 1-5
        c, stub, book, pf = ctx
        c.post(f"/books/{book['id']}/pdfs/{pf['id']}/extractions",
               json={"topic": "t", "pages_str": "1-5"})
        before = len(stub.calls)
        # When a conversation over "3-7" is created
        conv = c.post(f"/books/{book['id']}/conversations",
                      json={"pdf_file_id": pf["id"], "pages_str": "3-7"})
        # Then only pages 6,7 are newly OCR'd (3-5 hit the shared cache)
        assert conv.status_code == 201
        assert len(stub.calls) - before == 2

    def test_invalid_pages_returns_422(self, ctx):
        c, _, book, pf = ctx
        r = c.post(f"/books/{book['id']}/pdfs/{pf['id']}/extractions",
                   json={"topic": "t", "pages_str": "10-5"})
        assert r.status_code == 422

    def test_missing_pdf_returns_404(self, ctx):
        c, _, book, _ = ctx
        r = c.post(f"/books/{book['id']}/pdfs/nope/extractions",
                   json={"topic": "t", "pages_str": "1"})
        assert r.status_code == 404


class DescribeListAndDelete:
    def test_delete_removes_set_but_preserves_page_cache(self, ctx):
        # Given two extraction sets
        c, _, book, pf = ctx
        base = f"/books/{book['id']}/pdfs/{pf['id']}/extractions"
        e1 = c.post(base, json={"topic": "A", "pages_str": "1-2"}).json()
        c.post(base, json={"topic": "B", "pages_str": "3-4"})
        assert len(c.get(base).json()) == 2
        # When one set is deleted
        assert c.delete(f"{base}/{e1['id']}").status_code == 204
        # Then the set is gone but the shared page cache (1-4) remains
        assert len(c.get(base).json()) == 1
        assert _count_cached_pages(pf["id"]) == 4


class DescribeIndependence:
    def test_extraction_set_exists_without_any_conversation(self, ctx):
        # Given a set is created and no conversation
        c, _, book, pf = ctx
        r = c.post(f"/books/{book['id']}/pdfs/{pf['id']}/extractions",
                   json={"topic": "t", "pages_str": "1"})
        # Then the set exists independently (no conversation required)
        assert r.status_code == 201
        assert c.get(f"/books/{book['id']}/conversations").json() == []
