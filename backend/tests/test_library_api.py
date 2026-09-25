"""서재(Library) API BDD 명세."""
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


@pytest.fixture
def book_with_pdf(client, tmp_path):
    """책 1권 + PDF 파일 1개가 등록된 상태."""
    book = client.post("/books", json={"title": "테스트북"}).json()
    pdf = tmp_path / "ch1.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    pf = client.post(f"/books/{book['id']}/pdfs",
                     json={"label": "1부", "pdf_path": str(pdf)}).json()
    return book, pf


class DescribeBookManagement:
    """책 생성·조회·PDF 관리 동작 명세."""

    def test_create_book_returns_empty_pdf_list(self, client):
        # When a book is created
        r = client.post("/books", json={"title": "어텐션 메커니즘"})

        # Then the book is returned with an empty pdf_files list
        assert r.status_code == 201
        book = r.json()
        assert book["title"] == "어텐션 메커니즘"
        assert book["pdf_files"] == []

    def test_created_book_appears_in_list(self, client):
        # Given a book has been created
        book = client.post("/books", json={"title": "어텐션 메커니즘"}).json()

        # When all books are listed
        r = client.get("/books")

        # Then the new book is in the list
        assert r.status_code == 200
        assert any(b["id"] == book["id"] for b in r.json())

    def test_add_pdf_file_to_book(self, client, tmp_path):
        # Given an existing book and a real PDF file
        book = client.post("/books", json={"title": "테스트북"}).json()
        pdf = tmp_path / "ch1.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        # When the PDF is added
        r = client.post(f"/books/{book['id']}/pdfs",
                        json={"label": "1부", "pdf_path": str(pdf)})

        # Then the PDF record is returned with correct metadata
        assert r.status_code == 201
        pf = r.json()
        assert pf["label"] == "1부"
        assert pf["book_id"] == book["id"]

    def test_nonexistent_pdf_path_returns_404(self, client):
        # Given an existing book but a path that doesn't exist on disk
        book = client.post("/books", json={"title": "테스트북"}).json()

        # When that path is submitted
        r = client.post(f"/books/{book['id']}/pdfs",
                        json={"label": "x", "pdf_path": "/nonexistent/x.pdf"})

        # Then 404 is returned
        assert r.status_code == 404

    def test_delete_pdf_removes_it_from_book(self, client, book_with_pdf):
        # Given a book with one PDF
        book, pf = book_with_pdf

        # When the PDF is deleted
        r = client.delete(f"/books/{book['id']}/pdfs/{pf['id']}")

        # Then 204 is returned and the book's pdf_files is empty
        assert r.status_code == 204
        books = client.get("/books").json()
        book_data = next(b for b in books if b["id"] == book["id"])
        assert book_data["pdf_files"] == []
