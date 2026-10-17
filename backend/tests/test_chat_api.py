"""자유 대화 API BDD 명세."""
from __future__ import annotations

import app.db as db_mod
import pytest
from fastapi.testclient import TestClient

from app.domain.extractor import ExtractionResult, PageExtraction, Block, BBox, Highlight
from app.infrastructure import get_llm_client
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
    from app.presentation.chat_router import _extractor_dep, _llm_dep
    app.dependency_overrides[_extractor_dep] = lambda: _StubExtractor()
    app.dependency_overrides[_llm_dep] = lambda: get_llm_client(
        get_settings().__class__(**{**get_settings().__dict__, "llm_backend": "mock"})
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def conversation(client, tmp_path):
    """책 + PDF + 대화가 생성된 상태."""
    book = client.post("/books", json={"title": "테스트북"}).json()
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    pf = client.post(f"/books/{book['id']}/pdfs",
                     json={"label": "ch1", "pdf_path": str(pdf)}).json()
    conv = client.post(f"/books/{book['id']}/conversations",
                       json={"pdf_file_id": pf["id"], "pages_str": "1-2"}).json()
    return client, book, pf, conv


class DescribeCreateConversation:
    """POST /books/{id}/conversations 의 동작 명세."""

    def test_creates_conversation_with_parsed_pages(self, conversation):
        # Given a book with a PDF
        _, _, _, conv = conversation

        # Then the conversation has correct pages and display format
        assert conv["pages"] == [1, 2]
        assert conv["pages_display"] == "p.1-2"


class DescribeSendMessage:
    """POST /conversations/{id}/messages 의 동작 명세."""

    def test_returns_assistant_response(self, conversation):
        # Given an existing conversation
        client, _, _, conv = conversation

        # When a message is sent
        r = client.post(f"/conversations/{conv['id']}/messages",
                        json={"content": "셀프어텐션이란?"})

        # Then an assistant message is returned
        assert r.status_code == 200
        resp = r.json()
        assert resp["message"]["role"] == "assistant"
        assert resp["message"]["content"]

    def test_messages_are_accumulated_in_history(self, conversation):
        # Given two messages have been sent
        client, _, _, conv = conversation
        client.post(f"/conversations/{conv['id']}/messages", json={"content": "질문1"})
        client.post(f"/conversations/{conv['id']}/messages", json={"content": "질문2"})

        # When history is fetched
        msgs = client.get(f"/conversations/{conv['id']}/messages").json()

        # Then all 4 messages are in order: user1, asst1, user2, asst2
        assert len(msgs) == 4
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_invalid_pages_str_returns_422(self, client, tmp_path):
        # Given a reversed range
        book = client.post("/books", json={"title": "테스트북"}).json()
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        pf = client.post(f"/books/{book['id']}/pdfs",
                         json={"label": "ch1", "pdf_path": str(pdf)}).json()

        # When a conversation is created with an invalid page range
        r = client.post(f"/books/{book['id']}/conversations",
                        json={"pdf_file_id": pf["id"], "pages_str": "10-5"})

        # Then 422 is returned
        assert r.status_code == 422


class _HighlightExtractor:
    """노랑+초록 형광이 달린 PageExtraction 반환 (가중치 검증용)."""
    def extract(self, pdf_path, page_range):
        pe = PageExtraction(
            page=page_range[0], width_px=100, height_px=100, render_dpi=200,
            blocks=[Block(type="text", bbox=BBox(0, 0, 10, 10), text="content")],
            highlights=[Highlight("노랑구절", "yellow"), Highlight("초록구절", "green")],
        )
        return ExtractionResult(source=pdf_path, pages=[pe])


class DescribeChatHighlightWeighting:
    """use_highlights=true 시 색/가중치가 [HIGHLIGHTS_JSON]에 반영되는지 명세."""

    @pytest.fixture
    def hl_client(self):
        from app.main import app
        from app.presentation.chat_router import _extractor_dep, _llm_dep
        app.dependency_overrides[_extractor_dep] = lambda: _HighlightExtractor()
        app.dependency_overrides[_llm_dep] = lambda: get_llm_client(
            get_settings().__class__(**{**get_settings().__dict__, "llm_backend": "mock"})
        )
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()

    def test_stores_color_and_weight_with_green_above_yellow(self, hl_client, tmp_path):
        import json
        import sqlite3
        # Given a book + PDF
        book = hl_client.post("/books", json={"title": "b"}).json()
        pdf = tmp_path / "t.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        pf = hl_client.post(f"/books/{book['id']}/pdfs",
                            json={"label": "c", "pdf_path": str(pdf)}).json()

        # When a conversation opts into highlights
        conv = hl_client.post(f"/books/{book['id']}/conversations",
                              json={"pdf_file_id": pf["id"], "pages_str": "1", "use_highlights": True}).json()

        # Then the stored system message carries {text,color,weight} with green outweighing yellow
        conn = sqlite3.connect(db_mod._DB_PATH)
        conn.row_factory = sqlite3.Row
        content = conn.execute(
            "SELECT content FROM messages WHERE conversation_id=? AND role='system'", (conv["id"],)
        ).fetchone()["content"]
        conn.close()
        data = json.loads(content.split("[HIGHLIGHTS_JSON]", 1)[1])
        by_color = {d["color"]: d["weight"] for d in data}
        assert {d["text"] for d in data} == {"노랑구절", "초록구절"}
        assert by_color["green"] > by_color["yellow"]  # 초록이 더 높은 가중치
