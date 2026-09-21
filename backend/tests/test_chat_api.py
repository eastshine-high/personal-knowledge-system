"""T4 — 자유 대화 API 단위 테스트."""
from __future__ import annotations

import app.db as db_mod
import pytest
from fastapi.testclient import TestClient

from app.extractor import ExtractionResult, PageExtraction, Block, BBox
from app.extractors import get_extractor
from app.llm import get_llm_client
from app.config import get_settings


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_mod._DB_PATH = tmp_path / "test.db"
    if hasattr(db_mod._local, "conn"):
        db_mod._local.conn.close()
        del db_mod._local.conn
    yield
    if hasattr(db_mod._local, "conn"):
        db_mod._local.conn.close()
        del db_mod._local.conn


class _StubExtractor:
    """텍스트 블록 1개짜리 PageExtraction 반환."""
    def extract(self, pdf_path, page_range):
        page_num = page_range[0]
        pe = PageExtraction(
            page=page_num, width_px=100, height_px=100, render_dpi=200,
            blocks=[Block(type="text", bbox=BBox(0, 0, 10, 10), text=f"page{page_num} content")],
        )
        return ExtractionResult(source=pdf_path, pages=[pe])


@pytest.fixture
def client():
    from app.main import app
    from app.chat_router import _extractor_dep, _llm_dep
    app.dependency_overrides[_extractor_dep] = lambda: _StubExtractor()
    app.dependency_overrides[_llm_dep] = lambda: get_llm_client(
        get_settings().__class__(
            **{**get_settings().__dict__, "llm_backend": "mock"}
        )
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def book_and_pdf(client, tmp_path):
    book = client.post("/books", json={"title": "테스트북"}).json()
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    pf = client.post(f"/books/{book['id']}/pdfs",
                     json={"label": "ch1", "pdf_path": str(pdf)}).json()
    return book, pf


def test_create_conversation(client, book_and_pdf):
    book, pf = book_and_pdf
    r = client.post(f"/books/{book['id']}/conversations",
                    json={"pdf_file_id": pf["id"], "pages_str": "1-2"})
    assert r.status_code == 201
    conv = r.json()
    assert conv["pages"] == [1, 2]
    assert conv["pages_display"] == "p.1-2"


def test_send_message_returns_assistant(client, book_and_pdf):
    book, pf = book_and_pdf
    conv = client.post(f"/books/{book['id']}/conversations",
                       json={"pdf_file_id": pf["id"], "pages_str": "1"}).json()
    r = client.post(f"/conversations/{conv['id']}/messages",
                    json={"content": "셀프어텐션이란?"})
    assert r.status_code == 200
    resp = r.json()
    assert resp["message"]["role"] == "assistant"
    assert resp["message"]["content"]


def test_messages_history(client, book_and_pdf):
    book, pf = book_and_pdf
    conv = client.post(f"/books/{book['id']}/conversations",
                       json={"pdf_file_id": pf["id"], "pages_str": "1"}).json()
    client.post(f"/conversations/{conv['id']}/messages", json={"content": "질문1"})
    client.post(f"/conversations/{conv['id']}/messages", json={"content": "질문2"})

    r = client.get(f"/conversations/{conv['id']}/messages")
    msgs = r.json()
    assert len(msgs) == 4  # user1, asst1, user2, asst2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


def test_invalid_pages_str(client, book_and_pdf):
    book, pf = book_and_pdf
    r = client.post(f"/books/{book['id']}/conversations",
                    json={"pdf_file_id": pf["id"], "pages_str": "10-5"})
    assert r.status_code == 422
