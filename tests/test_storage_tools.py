import sqlite3

import pytest

from tools.storage_tools import (
    get_chunks,
    get_papers,
    get_statements,
    initialize_database,
    save_chunk,
    save_paper,
    save_statement,
)


def test_initialize_database_creates_expected_tables(tmp_path):
    db_path = tmp_path / "research.db"

    initialize_database(str(db_path))

    with sqlite3.connect(db_path) as conn:
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            ).fetchall()
        }

    assert {"papers", "chunks", "statements"}.issubset(table_names)


def test_save_and_get_paper_round_trip(tmp_path):
    db_path = tmp_path / "research.db"
    initialize_database(str(db_path))

    save_paper(
        str(db_path),
        paper_id="paper_001",
        title="Synthetic Paper",
        source_path="data/samples/synthetic_paper.txt",
        authors="A. Researcher; B. Scientist",
        year=2024,
        venue="Synthetic Workshop",
        license_notes="synthetic fixture",
    )

    assert get_papers(str(db_path)) == [
        {
            "paper_id": "paper_001",
            "title": "Synthetic Paper",
            "source_path": "data/samples/synthetic_paper.txt",
            "authors": "A. Researcher; B. Scientist",
            "year": 2024,
            "venue": "Synthetic Workshop",
            "license_notes": "synthetic fixture",
            "created_at": get_papers(str(db_path))[0]["created_at"],
        }
    ]


def test_save_paper_updates_existing_record(tmp_path):
    db_path = tmp_path / "research.db"
    initialize_database(str(db_path))

    save_paper(str(db_path), "paper_001", "Original", "original.pdf")
    save_paper(str(db_path), "paper_001", "Updated", "updated.pdf", year=2025)

    papers = get_papers(str(db_path))

    assert len(papers) == 1
    assert papers[0]["title"] == "Updated"
    assert papers[0]["source_path"] == "updated.pdf"
    assert papers[0]["year"] == 2025


def test_save_and_get_chunks_round_trip(tmp_path):
    db_path = tmp_path / "research.db"
    initialize_database(str(db_path))
    save_paper(str(db_path), "paper_001", "Synthetic Paper", "paper.txt")

    save_chunk(
        str(db_path),
        paper_id="paper_001",
        chunk_id="chunk_0000",
        chunk_index=0,
        text="first chunk",
        start_char=0,
        end_char=11,
    )
    save_chunk(
        str(db_path),
        paper_id="paper_001",
        chunk_id="chunk_0001",
        chunk_index=1,
        text="second chunk",
        start_char=8,
        end_char=20,
    )

    chunks = get_chunks(str(db_path), paper_id="paper_001")

    assert [chunk["chunk_id"] for chunk in chunks] == ["chunk_0000", "chunk_0001"]
    assert chunks[0]["text"] == "first chunk"
    assert chunks[1]["start_char"] == 8
    assert get_chunks(str(db_path), paper_id="missing") == []


def test_save_chunk_rejects_unknown_paper_id(tmp_path):
    db_path = tmp_path / "research.db"
    initialize_database(str(db_path))

    with pytest.raises(ValueError, match="Could not save chunk"):
        save_chunk(
            str(db_path),
            paper_id="missing",
            chunk_id="chunk_0000",
            chunk_index=0,
            text="orphan chunk",
            start_char=0,
            end_char=12,
        )


def test_save_and_get_statements_round_trip(tmp_path):
    db_path = tmp_path / "research.db"
    initialize_database(str(db_path))
    save_paper(str(db_path), "paper_001", "Synthetic Paper", "paper.txt")
    save_chunk(str(db_path), "paper_001", "paper_001:chunk_0000", 0, "We propose a method.", 0, 20)

    save_statement(
        str(db_path),
        statement_id="stmt_001",
        paper_id="paper_001",
        chunk_id="paper_001:chunk_0000",
        statement_type="method",
        statement_text="We propose a method.",
        evidence_text="We propose a method.",
        confidence_rule="rule:we propose",
    )

    statements = get_statements(str(db_path), paper_id="paper_001")

    assert statements == [
        {
            "statement_id": "stmt_001",
            "paper_id": "paper_001",
            "chunk_id": "paper_001:chunk_0000",
            "statement_type": "method",
            "statement_text": "We propose a method.",
            "evidence_text": "We propose a method.",
            "confidence_rule": "rule:we propose",
            "sentence_index": 0,
            "created_at": statements[0]["created_at"],
        }
    ]
    assert get_statements(str(db_path), paper_id="missing") == []


def test_save_statement_updates_existing_record(tmp_path):
    db_path = tmp_path / "research.db"
    initialize_database(str(db_path))
    save_paper(str(db_path), "paper_001", "Synthetic Paper", "paper.txt")
    save_chunk(str(db_path), "paper_001", "paper_001:chunk_0000", 0, "text", 0, 4)

    save_statement(
        str(db_path),
        "stmt_001",
        "paper_001",
        "paper_001:chunk_0000",
        "method",
        "Original statement.",
        "Original statement.",
        "rule:we propose",
    )
    save_statement(
        str(db_path),
        "stmt_001",
        "paper_001",
        "paper_001:chunk_0000",
        "result",
        "Updated statement.",
        "Updated statement.",
        "rule:achieves",
    )

    statements = get_statements(str(db_path))

    assert len(statements) == 1
    assert statements[0]["statement_type"] == "result"
    assert statements[0]["statement_text"] == "Updated statement."


def test_save_statement_rejects_unknown_chunk_id(tmp_path):
    db_path = tmp_path / "research.db"
    initialize_database(str(db_path))
    save_paper(str(db_path), "paper_001", "Synthetic Paper", "paper.txt")

    with pytest.raises(ValueError, match="Could not save statement"):
        save_statement(
            str(db_path),
            "stmt_001",
            "paper_001",
            "missing_chunk",
            "method",
            "We propose a method.",
            "We propose a method.",
            "rule:we propose",
        )


def test_storage_requires_initialized_database(tmp_path):
    db_path = tmp_path / "research.db"

    with pytest.raises(RuntimeError, match="Database is not initialized"):
        save_paper(str(db_path), "paper_001", "Title", "paper.pdf")


def test_storage_rejects_invalid_inputs(tmp_path):
    db_path = tmp_path / "research.db"
    initialize_database(str(db_path))

    with pytest.raises(ValueError, match="paper_id"):
        save_paper(str(db_path), "", "Title", "paper.pdf")

    with pytest.raises(ValueError, match="title"):
        save_paper(str(db_path), "paper_001", "", "paper.pdf")

    with pytest.raises(ValueError, match="chunk_index"):
        save_chunk(str(db_path), "paper_001", "chunk", -1, "text", 0, 4)

    with pytest.raises(ValueError, match="statement_type"):
        save_statement(
            str(db_path),
            "stmt_001",
            "paper_001",
            "chunk",
            "claim",
            "statement",
            "statement",
            "rule:test",
        )


def test_storage_rejects_remote_database_path():
    with pytest.raises(ValueError, match="Only local SQLite"):
        initialize_database("https://example.com/research.db")
