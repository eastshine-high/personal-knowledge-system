"""Sessions API 테스트 (B1~B3). 추출기·LLM은 dependency_overrides로 주입."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.api import _extractor_dep, _llm_dep
from app.extractor import BBox, Block, ExtractionResult, PageExtraction
from app.extractors.fixture_extractor import FixtureLayoutExtractor
from app.config import get_settings
from app.llm.client import MockLLMClient
from app.main import app


def _mock_llm():
    return MockLLMClient()


def _text_extractor():
    """텍스트 블록이 있는 가짜 추출 결과 반환 (pymupdf 불필요)."""
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
    """텍스트 블록이 없는 추출 결과 → EmptyTextError 유발."""
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


def test_create_session_ok():
    """mock 추출기 + mock LLM → 세션 생성 성공, session_id·notes·events 반환."""
    app.dependency_overrides[_extractor_dep] = _text_extractor
    app.dependency_overrides[_llm_dep] = _mock_llm
    client = TestClient(app)

    resp = client.post("/sessions", json={
        "pdf_path": "dummy.pdf",
        "page_start": 200,
        "page_end": 200,
        "topic": "셀프 어텐션",
    })

    assert resp.status_code == 201
    data = resp.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 0
    assert len(data["notes"]) >= 1
    note = data["notes"][0]
    assert note["title"]
    assert note["markdown"].startswith("---")   # 프론트매터 포함
    assert len(data["events"]) >= 1
    assert data["events"][0]["action"] == "start"


def test_create_session_empty_text():
    """텍스트 없는 추출 결과 → 422."""
    app.dependency_overrides[_extractor_dep] = _empty_extractor
    app.dependency_overrides[_llm_dep] = _mock_llm
    client = TestClient(app)

    resp = client.post("/sessions", json={
        "pdf_path": "dummy.pdf",
        "page_start": 1,
        "page_end": 1,
        "topic": "테스트",
    })

    assert resp.status_code == 422


def test_get_notes():
    """세션 생성 후 GET /notes → 노트 목록 반환."""
    app.dependency_overrides[_extractor_dep] = _text_extractor
    app.dependency_overrides[_llm_dep] = _mock_llm
    client = TestClient(app)

    sid = client.post("/sessions", json={
        "pdf_path": "dummy.pdf", "page_start": 1, "page_end": 1, "topic": "테스트",
    }).json()["session_id"]

    resp = client.get(f"/sessions/{sid}/notes")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_refine_session():
    """refine → 노트 갱신 + events에 refine 추가."""
    app.dependency_overrides[_extractor_dep] = _text_extractor
    app.dependency_overrides[_llm_dep] = _mock_llm
    client = TestClient(app)

    sid = client.post("/sessions", json={
        "pdf_path": "dummy.pdf", "page_start": 1, "page_end": 1, "topic": "테스트",
    }).json()["session_id"]

    resp = client.post(f"/sessions/{sid}/refine", json={"instruction": "불릿으로"})
    assert resp.status_code == 200
    data = resp.json()
    actions = [e["action"] for e in data["events"]]
    assert "refine" in actions


def test_edit_note():
    """apply_edit → 노트 본문 갱신."""
    app.dependency_overrides[_extractor_dep] = _text_extractor
    app.dependency_overrides[_llm_dep] = _mock_llm
    client = TestClient(app)

    create = client.post("/sessions", json={
        "pdf_path": "dummy.pdf", "page_start": 1, "page_end": 1, "topic": "테스트",
    }).json()
    sid = create["session_id"]
    note_id = create["notes"][0]["id"]

    resp = client.post(f"/sessions/{sid}/notes/{note_id}/edit",
                       json={"body": "직접 수정한 내용"})
    assert resp.status_code == 200
    assert resp.json()["body"] == "직접 수정한 내용"


def test_undo_session():
    """refine 후 undo → 이전 노트 복원."""
    app.dependency_overrides[_extractor_dep] = _text_extractor
    app.dependency_overrides[_llm_dep] = _mock_llm
    client = TestClient(app)

    create = client.post("/sessions", json={
        "pdf_path": "dummy.pdf", "page_start": 1, "page_end": 1, "topic": "테스트",
    }).json()
    sid = create["session_id"]
    original_body = create["notes"][0]["body"]

    client.post(f"/sessions/{sid}/refine", json={"instruction": "불릿으로"})
    resp = client.post(f"/sessions/{sid}/undo")
    assert resp.status_code == 200
    assert resp.json()["notes"][0]["body"] == original_body


def test_undo_without_prior_returns_409():
    """undo 가능한 이전 상태 없음 → 409."""
    app.dependency_overrides[_extractor_dep] = _text_extractor
    app.dependency_overrides[_llm_dep] = _mock_llm
    client = TestClient(app)

    sid = client.post("/sessions", json={
        "pdf_path": "dummy.pdf", "page_start": 1, "page_end": 1, "topic": "테스트",
    }).json()["session_id"]

    resp = client.post(f"/sessions/{sid}/undo")
    assert resp.status_code == 409


def test_session_not_found():
    """없는 session_id → 404."""
    client = TestClient(app)
    assert client.get("/sessions/nonexistent/notes").status_code == 404


def test_export_session():
    """세션 내보내기 → zip 파일 다운로드."""
    import zipfile, io
    app.dependency_overrides[_extractor_dep] = _text_extractor
    app.dependency_overrides[_llm_dep] = _mock_llm
    client = TestClient(app)

    sid = client.post("/sessions", json={
        "pdf_path": "dummy.pdf", "page_start": 1, "page_end": 1, "topic": "테스트",
    }).json()["session_id"]

    resp = client.get(f"/sessions/{sid}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert any(n.endswith(".md") for n in names)   # 마크다운 파일 포함


def _make_pdf(path: Path) -> None:
    """테스트용 단일 페이지 PDF 생성."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((100, 100), "Test page content")
    doc.save(str(path))
    doc.close()


def test_get_page_image(tmp_path):
    """세션 생성 후 페이지 이미지 요청 → PNG 반환."""
    pdf_path = tmp_path / "test.pdf"
    _make_pdf(pdf_path)

    app.dependency_overrides[_extractor_dep] = _text_extractor
    app.dependency_overrides[_llm_dep] = _mock_llm
    client = TestClient(app)

    sid = client.post("/sessions", json={
        "pdf_path": str(pdf_path), "page_start": 1, "page_end": 1, "topic": "테스트",
    }).json()["session_id"]

    resp = client.get(f"/sessions/{sid}/pages/1")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert len(resp.content) > 1000   # 비어있지 않은 PNG


def test_get_page_image_out_of_range(tmp_path):
    """페이지 번호 범위 초과 → 404."""
    pdf_path = tmp_path / "test.pdf"
    _make_pdf(pdf_path)

    app.dependency_overrides[_extractor_dep] = _text_extractor
    app.dependency_overrides[_llm_dep] = _mock_llm
    client = TestClient(app)

    sid = client.post("/sessions", json={
        "pdf_path": str(pdf_path), "page_start": 1, "page_end": 1, "topic": "테스트",
    }).json()["session_id"]

    assert client.get(f"/sessions/{sid}/pages/99").status_code == 404


def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
