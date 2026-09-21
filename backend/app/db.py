"""SQLite 연결 및 스키마 초기화.

DB 파일: backend/pks.db (gitignored).
init_db()는 앱 시작 시 한 번 호출 — CREATE TABLE IF NOT EXISTS로 멱등.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parents[1] / "pks.db"
_local = threading.local()


def get_db() -> sqlite3.Connection:
    """스레드-로컬 SQLite 커넥션 반환. row_factory=Row로 컬럼명 접근 가능."""
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(str(_DB_PATH))
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA foreign_keys = ON")
    return _local.conn


def init_db() -> None:
    """모든 테이블을 멱등하게 생성. 앱 시작 시 호출."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS books (
            id         TEXT PRIMARY KEY,
            title      TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pdf_files (
            id         TEXT PRIMARY KEY,
            book_id    TEXT NOT NULL REFERENCES books(id),
            label      TEXT NOT NULL,
            pdf_path   TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS page_extractions (
            pdf_file_id TEXT    NOT NULL,
            page_num    INTEGER NOT NULL,
            json        TEXT    NOT NULL,
            created_at  TEXT    NOT NULL,
            PRIMARY KEY (pdf_file_id, page_num)
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id          TEXT PRIMARY KEY,
            book_id     TEXT NOT NULL REFERENCES books(id),
            pdf_file_id TEXT NOT NULL REFERENCES pdf_files(id),
            pages_json  TEXT NOT NULL,
            title       TEXT,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id              TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id),
            role            TEXT NOT NULL,
            content         TEXT NOT NULL,
            created_at      TEXT NOT NULL
        );
    """)
    conn.commit()
