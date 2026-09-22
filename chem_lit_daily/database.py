from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable


APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "literature.db"


@contextmanager
def connect() -> Iterable[sqlite3.Connection]:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS papers (
                id TEXT PRIMARY KEY,
                doi TEXT,
                title TEXT NOT NULL,
                journal TEXT,
                publication_date TEXT,
                authors TEXT,
                abstract TEXT,
                url TEXT,
                cited_by_count INTEGER DEFAULT 0,
                keywords TEXT,
                impact_score REAL DEFAULT 0,
                summary TEXT,
                fetched_at TEXT NOT NULL,
                user_rating INTEGER,
                user_note TEXT DEFAULT '',
                hidden INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS collection_papers (
                collection_id INTEGER NOT NULL,
                paper_id TEXT NOT NULL,
                added_at TEXT NOT NULL,
                PRIMARY KEY (collection_id, paper_id),
                FOREIGN KEY (collection_id) REFERENCES collections(id),
                FOREIGN KEY (paper_id) REFERENCES papers(id)
            );
            """
        )


def get_setting(key: str, default: Any = None) -> Any:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if not row:
            return default
        return json.loads(row["value"])


def set_setting(key: str, value: Any) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )


def upsert_paper(paper: dict[str, Any]) -> None:
    columns = [
        "id",
        "doi",
        "title",
        "journal",
        "publication_date",
        "authors",
        "abstract",
        "url",
        "cited_by_count",
        "keywords",
        "impact_score",
        "summary",
        "fetched_at",
    ]
    values = [paper.get(column) for column in columns]
    placeholders = ", ".join("?" for _ in columns)
    update_clause = ", ".join(
        f"{column} = excluded.{column}" for column in columns if column != "id"
    )
    with connect() as conn:
        conn.execute(
            f"""
            INSERT INTO papers ({", ".join(columns)}) VALUES ({placeholders})
            ON CONFLICT(id) DO UPDATE SET {update_clause}
            """,
            values,
        )


def list_papers(
    *,
    search: str = "",
    min_score: float = 0,
    only_rated: bool = False,
    only_unread: bool = False,
    limit: int = 200,
) -> list[sqlite3.Row]:
    clauses = ["hidden = 0", "impact_score >= ?"]
    params: list[Any] = [min_score]
    if search:
        clauses.append("(title LIKE ? OR journal LIKE ? OR abstract LIKE ? OR keywords LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like, like])
    if only_rated:
        clauses.append("user_rating IS NOT NULL")
    if only_unread:
        clauses.append("user_rating IS NULL")
    params.append(limit)
    with connect() as conn:
        return conn.execute(
            f"""
            SELECT * FROM papers
            WHERE {" AND ".join(clauses)}
            ORDER BY publication_date DESC, impact_score DESC
            LIMIT ?
            """,
            params,
        ).fetchall()


def update_rating(paper_id: str, rating: int | None, note: str = "") -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE papers SET user_rating = ?, user_note = ? WHERE id = ?",
            (rating, note, paper_id),
        )


def hide_paper(paper_id: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE papers SET hidden = 1 WHERE id = ?", (paper_id,))


def create_collection(name: str) -> None:
    from datetime import datetime

    if not name.strip():
        return
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO collections(name, created_at) VALUES(?, ?)",
            (name.strip(), datetime.now().isoformat(timespec="seconds")),
        )


def list_collections() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM collections ORDER BY name").fetchall()


def add_to_collection(collection_id: int, paper_id: str) -> None:
    from datetime import datetime

    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO collection_papers(collection_id, paper_id, added_at) VALUES(?, ?, ?)",
            (collection_id, paper_id, datetime.now().isoformat(timespec="seconds")),
        )


def papers_in_collection(collection_id: int) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            """
            SELECT p.*, cp.added_at
            FROM collection_papers cp
            JOIN papers p ON p.id = cp.paper_id
            WHERE cp.collection_id = ? AND p.hidden = 0
            ORDER BY cp.added_at DESC
            """,
            (collection_id,),
        ).fetchall()
