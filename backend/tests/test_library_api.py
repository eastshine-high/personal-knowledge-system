"""T3 — 서재 API 단위 테스트."""
from __future__ import annotations

import app.db as db_mod
import pytest
from fastapi.testclient import TestClient


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


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_create_and_list_book(client):
    r = client.post("/books", json={"title": "어텐션 메커니즘"})
    assert r.status_code == 201
    book = r.json()
    assert book["title"] == "어텐션 메커니즘"
    assert book["pdf_files"] == []

    r2 = client.get("/books")
    assert r2.status_code == 200
    assert any(b["id"] == book["id"] for b in r2.json())


def test_add_pdf_file(client, tmp_path):
    book = client.post("/books", json={"title": "테스트북"}).json()
    pdf = tmp_path / "ch1.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    r = client.post(f"/books/{book['id']}/pdfs",
                    json={"label": "1부", "pdf_path": str(pdf)})
    assert r.status_code == 201
    pf = r.json()
    assert pf["label"] == "1부"
    assert pf["book_id"] == book["id"]


def test_add_pdf_nonexistent_path_returns_404(client):
    book = client.post("/books", json={"title": "테스트북"}).json()
    r = client.post(f"/books/{book['id']}/pdfs",
                    json={"label": "x", "pdf_path": "/nonexistent/x.pdf"})
    assert r.status_code == 404


def test_delete_pdf(client, tmp_path):
    book = client.post("/books", json={"title": "테스트북"}).json()
    pdf = tmp_path / "ch1.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    pf = client.post(f"/books/{book['id']}/pdfs",
                     json={"label": "1부", "pdf_path": str(pdf)}).json()

    r = client.delete(f"/books/{book['id']}/pdfs/{pf['id']}")
    assert r.status_code == 204

    books = client.get("/books").json()
    book_data = next(b for b in books if b["id"] == book["id"])
    assert book_data["pdf_files"] == []
