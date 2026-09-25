"""Sessions API BDD 명세 (B1~B3). 추출기·LLM은 dependency_overrides로 주입."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.api import _extractor_dep, _llm_dep
from app.extractor import BBox, Block, ExtractionResult, PageExtraction
from app.config import get_settings
from app.llm.client import MockLLMClient
from app.main import app


# ---------------------------------------------------------------------------
# 공용 helpers / fixtures
# ---------------------------------------------------------------------------

def _mock_llm():
    return MockLLMClient()


def _text_extractor():
    """텍스트 블록이 있는 가짜 추출 결과 — pymupdf 불필요."""
    mock = MagicMock()
    mock.extract.return_value = ExtractionResult(
        source="dummy.pdf",
        pages=[PageExtraction(
            page=1, width_px=800, height_px=1200, render_dpi=200,
            blocks=[Block(type="text", bbox=BBox(0, 0, 400, 30), reading_order=0,
                          text="셀프 어텐션은 시퀀스 내 토큰 간 관계를 계산한다.")],
        )],
    )
    return mock


def _empty_extractor():
    """텍스트 블록 없는 추출 결과 → EmptyTextError 유발."""
    mock = MagicMock()
    mock.extract.return_value = ExtractionResult(
        source="dummy.pdf",
        pages=[PageExtraction(page=1, width_px=100, height_px=100, render_dpi=200, blocks=[])],
    )
    return mock


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client_with_text():
    app.dependency_overrides[_extractor_dep] = _text_extractor
    app.dependency_overrides[_llm_dep] = _mock_llm
    return TestClient(app)


@pytest.fixture
def created_session(client_with_text):
    """세션이 이미 생성된 상태의 (client, session_data) 튜플."""
    data = client_with_text.post("/sessions", json={
        "pdf_path": "dummy.pdf", "page_start": 1, "page_end": 1, "topic": "테스트",
    }).json()
    return client_with_text, data


def _make_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((100, 100), "Test page content")
    doc.save(str(path))
    doc.close()


# ---------------------------------------------------------------------------
# Describe: 세션 생성
# ---------------------------------------------------------------------------

class DescribeCreateSession:
    """POST /sessions 의 동작 명세."""

    def test_returns_session_with_notes_and_events(self, client_with_text):
        # When a session is created with a valid PDF and topic
        resp = client_with_text.post("/sessions", json={
            "pdf_path": "dummy.pdf", "page_start": 200, "page_end": 200, "topic": "셀프 어텐션",
        })

        # Then 201 is returned with session_id, at least one note, and a start event
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["session_id"]) > 0
        assert len(data["notes"]) >= 1
        assert data["notes"][0]["markdown"].startswith("---")   # 프론트매터 포함
        assert data["events"][0]["action"] == "start"

    def test_pdf_with_no_text_returns_422(self):
        # Given an extractor that returns no text blocks
        app.dependency_overrides[_extractor_dep] = _empty_extractor
        app.dependency_overrides[_llm_dep] = _mock_llm
        client = TestClient(app)

        # When a session is created
        resp = client.post("/sessions", json={
            "pdf_path": "dummy.pdf", "page_start": 1, "page_end": 1, "topic": "테스트",
        })

        # Then 422 is returned
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Describe: 세션 조작
# ---------------------------------------------------------------------------

class DescribeSessionOperations:
    """세션 조회·리파인·편집·undo 동작 명세."""

    def test_get_notes_returns_note_list(self, created_session):
        # Given a created session
        client, data = created_session
        sid = data["session_id"]

        # When notes are fetched
        resp = client.get(f"/sessions/{sid}/notes")

        # Then the list is returned
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_refine_updates_notes_and_appends_refine_event(self, created_session):
        # Given a created session
        client, data = created_session
        sid = data["session_id"]

        # When refined
        resp = client.post(f"/sessions/{sid}/refine", json={"instruction": "불릿으로"})

        # Then the response contains a refine event
        assert resp.status_code == 200
        actions = [e["action"] for e in resp.json()["events"]]
        assert "refine" in actions

    def test_edit_note_updates_body(self, created_session):
        # Given a created session
        client, data = created_session
        sid = data["session_id"]
        note_id = data["notes"][0]["id"]

        # When the note is directly edited
        resp = client.post(f"/sessions/{sid}/notes/{note_id}/edit",
                           json={"body": "직접 수정한 내용"})

        # Then the updated body is returned
        assert resp.status_code == 200
        assert resp.json()["body"] == "직접 수정한 내용"

    def test_undo_restores_note_to_state_before_refine(self, created_session):
        # Given a session that has been refined
        client, data = created_session
        sid = data["session_id"]
        original_body = data["notes"][0]["body"]
        client.post(f"/sessions/{sid}/refine", json={"instruction": "불릿으로"})

        # When undone
        resp = client.post(f"/sessions/{sid}/undo")

        # Then the note is back to the original body
        assert resp.status_code == 200
        assert resp.json()["notes"][0]["body"] == original_body

    def test_undo_without_prior_state_returns_409(self, client_with_text):
        # Given a fresh session (no changes after start)
        sid = client_with_text.post("/sessions", json={
            "pdf_path": "dummy.pdf", "page_start": 1, "page_end": 1, "topic": "테스트",
        }).json()["session_id"]

        # When undo is attempted
        resp = client_with_text.post(f"/sessions/{sid}/undo")

        # Then 409 Conflict is returned
        assert resp.status_code == 409

    def test_unknown_session_id_returns_404(self):
        # Given no session with id "nonexistent"
        client = TestClient(app)

        # Then 404 is returned
        assert client.get("/sessions/nonexistent/notes").status_code == 404


# ---------------------------------------------------------------------------
# Describe: export + 페이지 이미지
# ---------------------------------------------------------------------------

class DescribeSessionExportAndImages:
    """세션 zip 내보내기 + 페이지 이미지 반환 동작 명세."""

    def test_export_returns_zip_with_markdown(self, created_session):
        import zipfile, io
        # Given a created session
        client, data = created_session
        sid = data["session_id"]

        # When exported
        resp = client.get(f"/sessions/{sid}/export")

        # Then a zip file is returned containing at least one markdown file
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        assert any(n.endswith(".md") for n in zf.namelist())

    def test_page_image_returns_png(self, tmp_path, client_with_text):
        # Given a real PDF file
        pdf_path = tmp_path / "test.pdf"
        _make_pdf(pdf_path)
        sid = client_with_text.post("/sessions", json={
            "pdf_path": str(pdf_path), "page_start": 1, "page_end": 1, "topic": "테스트",
        }).json()["session_id"]

        # When the first page image is requested
        resp = client_with_text.get(f"/sessions/{sid}/pages/1")

        # Then a non-empty PNG is returned
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert len(resp.content) > 1000

    def test_page_image_out_of_range_returns_404(self, tmp_path, client_with_text):
        # Given a single-page PDF
        pdf_path = tmp_path / "test.pdf"
        _make_pdf(pdf_path)
        sid = client_with_text.post("/sessions", json={
            "pdf_path": str(pdf_path), "page_start": 1, "page_end": 1, "topic": "테스트",
        }).json()["session_id"]

        # When a non-existent page number is requested
        resp = client_with_text.get(f"/sessions/{sid}/pages/99")

        # Then 404 is returned
        assert resp.status_code == 404
