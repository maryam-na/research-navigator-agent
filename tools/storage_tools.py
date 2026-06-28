"""SQLite storage helpers for local papers and text chunks."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import urlparse


def _resolve_db_path(db_path: str) -> Path:
    if not db_path or not db_path.strip():
        raise ValueError("db_path must be a non-empty local file path.")

    parsed = urlparse(db_path)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError("Only local SQLite database paths are supported.")

    path = Path(parsed.path if parsed.scheme == "file" else db_path).expanduser()
    if path.exists() and path.is_dir():
        raise ValueError(f"Database path points to a directory: {path}")
    return path


def _connect(db_path: str) -> sqlite3.Connection:
    path = _resolve_db_path(db_path)
    if path.parent and not path.parent.exists():
        raise FileNotFoundError(f"Database directory does not exist: {path.parent}")

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def initialize_database(db_path: str) -> None:
    """Create the local SQLite schema if it does not already exist."""

    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source_path TEXT NOT NULL,
                authors TEXT,
                year INTEGER,
                venue TEXT,
                license_notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                paper_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                start_char INTEGER NOT NULL,
                end_char INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE,
                UNIQUE (paper_id, chunk_index),
                CHECK (chunk_index >= 0),
                CHECK (start_char >= 0),
                CHECK (end_char >= start_char)
            );

            CREATE TABLE IF NOT EXISTS statements (
                statement_id TEXT PRIMARY KEY,
                paper_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                statement_type TEXT NOT NULL,
                statement_text TEXT NOT NULL,
                evidence_text TEXT NOT NULL,
                confidence_rule TEXT NOT NULL,
                sentence_index INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE,
                FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE
            );
            """
        )


def save_paper(
    db_path: str,
    paper_id: str,
    title: str,
    source_path: str,
    authors: str | None = None,
    year: int | None = None,
    venue: str | None = None,
    license_notes: str | None = None,
) -> None:
    """Insert or update a paper record."""

    if not paper_id or not paper_id.strip():
        raise ValueError("paper_id must be a non-empty string.")
    if not title or not title.strip():
        raise ValueError("title must be a non-empty string.")
    if not source_path or not source_path.strip():
        raise ValueError("source_path must be a non-empty string.")
    if year is not None and (year < 0 or year > 9999):
        raise ValueError("year must be between 0 and 9999 when provided.")

    with _connect(db_path) as conn:
        try:
            conn.execute(
                """
                INSERT INTO papers (
                    paper_id, title, source_path, authors, year, venue, license_notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(paper_id) DO UPDATE SET
                    title = excluded.title,
                    source_path = excluded.source_path,
                    authors = excluded.authors,
                    year = excluded.year,
                    venue = excluded.venue,
                    license_notes = excluded.license_notes
                """,
                (
                    paper_id.strip(),
                    title.strip(),
                    source_path.strip(),
                    authors.strip() if authors else None,
                    year,
                    venue.strip() if venue else None,
                    license_notes.strip() if license_notes else None,
                ),
            )
        except sqlite3.OperationalError as exc:
            raise RuntimeError("Database is not initialized. Call initialize_database first.") from exc


def save_chunk(
    db_path: str,
    paper_id: str,
    chunk_id: str,
    chunk_index: int,
    text: str,
    start_char: int,
    end_char: int,
) -> None:
    """Insert or update a text chunk for a saved paper."""

    if not paper_id or not paper_id.strip():
        raise ValueError("paper_id must be a non-empty string.")
    if not chunk_id or not chunk_id.strip():
        raise ValueError("chunk_id must be a non-empty string.")
    if chunk_index < 0:
        raise ValueError("chunk_index must be greater than or equal to 0.")
    if not isinstance(text, str) or not text:
        raise ValueError("text must be a non-empty string.")
    if start_char < 0:
        raise ValueError("start_char must be greater than or equal to 0.")
    if end_char < start_char:
        raise ValueError("end_char must be greater than or equal to start_char.")

    with _connect(db_path) as conn:
        try:
            conn.execute(
                """
                INSERT INTO chunks (
                    chunk_id, paper_id, chunk_index, text, start_char, end_char
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    paper_id = excluded.paper_id,
                    chunk_index = excluded.chunk_index,
                    text = excluded.text,
                    start_char = excluded.start_char,
                    end_char = excluded.end_char
                """,
                (
                    chunk_id.strip(),
                    paper_id.strip(),
                    chunk_index,
                    text,
                    start_char,
                    end_char,
                ),
            )
        except sqlite3.OperationalError as exc:
            raise RuntimeError("Database is not initialized. Call initialize_database first.") from exc
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Could not save chunk for paper_id '{paper_id}'.") from exc


def get_papers(db_path: str) -> list[dict]:
    """Return saved papers ordered by creation time and paper id."""

    with _connect(db_path) as conn:
        try:
            rows = conn.execute(
                """
                SELECT paper_id, title, source_path, authors, year, venue, license_notes, created_at
                FROM papers
                ORDER BY created_at, paper_id
                """
            ).fetchall()
        except sqlite3.OperationalError as exc:
            raise RuntimeError("Database is not initialized. Call initialize_database first.") from exc
    return _rows_to_dicts(rows)


def get_chunks(db_path: str, paper_id: str | None = None) -> list[dict]:
    """Return saved chunks ordered by paper and chunk index."""

    with _connect(db_path) as conn:
        try:
            if paper_id is None:
                rows = conn.execute(
                    """
                    SELECT chunk_id, paper_id, chunk_index, text, start_char, end_char, created_at
                    FROM chunks
                    ORDER BY paper_id, chunk_index
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT chunk_id, paper_id, chunk_index, text, start_char, end_char, created_at
                    FROM chunks
                    WHERE paper_id = ?
                    ORDER BY chunk_index
                    """,
                    (paper_id,),
                ).fetchall()
        except sqlite3.OperationalError as exc:
            raise RuntimeError("Database is not initialized. Call initialize_database first.") from exc
    return _rows_to_dicts(rows)


def save_statement(
    db_path: str,
    statement_id: str,
    paper_id: str,
    chunk_id: str,
    statement_type: str,
    statement_text: str,
    evidence_text: str,
    confidence_rule: str,
    sentence_index: int = 0,
) -> None:
    """Insert or update an extracted research statement."""

    allowed_types = {
        "method",
        "result",
        "limitation",
        "future_work",
        "dataset",
        "background",
        "unknown",
    }
    if not statement_id or not statement_id.strip():
        raise ValueError("statement_id must be a non-empty string.")
    if not paper_id or not paper_id.strip():
        raise ValueError("paper_id must be a non-empty string.")
    if not chunk_id or not chunk_id.strip():
        raise ValueError("chunk_id must be a non-empty string.")
    if statement_type not in allowed_types:
        raise ValueError(f"statement_type must be one of: {', '.join(sorted(allowed_types))}.")
    if not statement_text or not statement_text.strip():
        raise ValueError("statement_text must be a non-empty string.")
    if not evidence_text or not evidence_text.strip():
        raise ValueError("evidence_text must be a non-empty string.")
    if not confidence_rule or not confidence_rule.strip():
        raise ValueError("confidence_rule must be a non-empty string.")
    if sentence_index < 0:
        raise ValueError("sentence_index must be greater than or equal to 0.")

    with _connect(db_path) as conn:
        try:
            conn.execute(
                """
                INSERT INTO statements (
                    statement_id,
                    paper_id,
                    chunk_id,
                    statement_type,
                    statement_text,
                    evidence_text,
                    confidence_rule,
                    sentence_index
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(statement_id) DO UPDATE SET
                    paper_id = excluded.paper_id,
                    chunk_id = excluded.chunk_id,
                    statement_type = excluded.statement_type,
                    statement_text = excluded.statement_text,
                    evidence_text = excluded.evidence_text,
                    confidence_rule = excluded.confidence_rule,
                    sentence_index = excluded.sentence_index
                """,
                (
                    statement_id.strip(),
                    paper_id.strip(),
                    chunk_id.strip(),
                    statement_type,
                    statement_text.strip(),
                    evidence_text.strip(),
                    confidence_rule.strip(),
                    sentence_index,
                ),
            )
        except sqlite3.OperationalError as exc:
            raise RuntimeError("Database is not initialized. Call initialize_database first.") from exc
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Could not save statement for paper_id '{paper_id}' and chunk_id '{chunk_id}'."
            ) from exc


def get_statements(db_path: str, paper_id: str | None = None) -> list[dict]:
    """Return extracted statements ordered by paper, chunk, and statement id."""

    with _connect(db_path) as conn:
        try:
            if paper_id is None:
                rows = conn.execute(
                    """
                    SELECT
                        statement_id,
                        paper_id,
                        chunk_id,
                        statement_type,
                        statement_text,
                        evidence_text,
                        confidence_rule,
                        sentence_index,
                        created_at
                    FROM statements
                    ORDER BY paper_id, chunk_id, sentence_index, statement_id
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        statement_id,
                        paper_id,
                        chunk_id,
                        statement_type,
                        statement_text,
                        evidence_text,
                        confidence_rule,
                        sentence_index,
                        created_at
                    FROM statements
                    WHERE paper_id = ?
                    ORDER BY chunk_id, sentence_index, statement_id
                    """,
                    (paper_id,),
                ).fetchall()
        except sqlite3.OperationalError as exc:
            raise RuntimeError("Database is not initialized. Call initialize_database first.") from exc
    return _rows_to_dicts(rows)
