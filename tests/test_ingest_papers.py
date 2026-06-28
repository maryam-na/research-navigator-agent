import subprocess
import sys

import pytest

from scripts import ingest_papers
from tools.storage_tools import get_chunks, get_papers, get_statements


def test_ingest_empty_folder_creates_database_and_reports_zero(tmp_path, capsys):
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    db_path = tmp_path / "processed" / "papers.sqlite"

    summary = ingest_papers.ingest_papers(str(papers_dir), str(db_path))

    assert summary == ingest_papers.IngestionSummary(papers=0, chunks=0, skipped_files=0)
    assert db_path.exists()
    assert get_papers(str(db_path)) == []
    assert get_chunks(str(db_path)) == []
    assert "Ingested 0 papers, 0 chunks, 0 statements, skipped 0 files." in capsys.readouterr().out


def test_ingest_creates_processed_directory_and_saves_pdf_chunks(tmp_path, monkeypatch):
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    (papers_dir / "paper-01.pdf").write_bytes(b"not a real pdf; extraction is mocked")
    db_path = tmp_path / "nested" / "processed" / "papers.sqlite"

    def fake_extract_pdf_text(pdf_path: str) -> str:
        assert pdf_path.endswith("paper-01.pdf")
        return "abcdefghij" * 150

    monkeypatch.setattr(ingest_papers.pdf_tools, "extract_pdf_text", fake_extract_pdf_text)

    summary = ingest_papers.ingest_papers(str(papers_dir), str(db_path))

    assert db_path.parent.exists()
    assert summary.papers == 1
    assert summary.chunks == 2
    assert summary.skipped_files == 0
    assert summary.statements == 0

    papers = get_papers(str(db_path))
    chunks = get_chunks(str(db_path), paper_id="paper-01")

    assert papers[0]["paper_id"] == "paper-01"
    assert papers[0]["title"] == "paper 01"
    assert papers[0]["source_path"].endswith("paper-01.pdf")
    assert [chunk["chunk_id"] for chunk in chunks] == [
        "paper-01:chunk_0000",
        "paper-01:chunk_0001",
    ]


def test_ingest_ignores_non_pdf_files(tmp_path, monkeypatch):
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    (papers_dir / "notes.txt").write_text("not a PDF", encoding="utf-8")
    db_path = tmp_path / "processed" / "papers.sqlite"

    def fail_if_called(_pdf_path: str) -> str:
        raise AssertionError("non-PDF files should not be extracted")

    monkeypatch.setattr(ingest_papers.pdf_tools, "extract_pdf_text", fail_if_called)

    summary = ingest_papers.ingest_papers(str(papers_dir), str(db_path))

    assert summary == ingest_papers.IngestionSummary(
        papers=0,
        chunks=0,
        skipped_files=0,
        statements=0,
    )
    assert get_papers(str(db_path)) == []


def test_ingest_skips_invalid_pdf_safely(tmp_path, monkeypatch, capsys):
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    (papers_dir / "broken.pdf").write_bytes(b"not a real pdf")
    db_path = tmp_path / "processed" / "papers.sqlite"

    def fake_extract_pdf_text(_pdf_path: str) -> str:
        raise ValueError("Could not extract text from PDF")

    monkeypatch.setattr(ingest_papers.pdf_tools, "extract_pdf_text", fake_extract_pdf_text)

    summary = ingest_papers.ingest_papers(str(papers_dir), str(db_path))

    assert summary == ingest_papers.IngestionSummary(
        papers=0,
        chunks=0,
        skipped_files=1,
        statements=0,
    )
    assert get_papers(str(db_path)) == []
    output = capsys.readouterr().out
    assert "Skipped broken.pdf: Could not extract text from PDF" in output
    assert "Ingested 0 papers, 0 chunks, 0 statements, skipped 1 files." in output


def test_ingest_skips_pdf_with_no_extractable_text(tmp_path, monkeypatch, capsys):
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    (papers_dir / "empty.pdf").write_bytes(b"not a real pdf")
    db_path = tmp_path / "processed" / "papers.sqlite"

    monkeypatch.setattr(ingest_papers.pdf_tools, "extract_pdf_text", lambda _path: "")

    summary = ingest_papers.ingest_papers(str(papers_dir), str(db_path))

    assert summary == ingest_papers.IngestionSummary(
        papers=0,
        chunks=0,
        skipped_files=1,
        statements=0,
    )
    assert "Skipped empty.pdf: no extractable text." in capsys.readouterr().out


def test_ingest_extracts_and_saves_statements_when_flag_enabled(tmp_path, monkeypatch):
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    (papers_dir / "paper-01.pdf").write_bytes(b"not a real pdf; extraction is mocked")
    db_path = tmp_path / "processed" / "papers.sqlite"

    monkeypatch.setattr(
        ingest_papers.pdf_tools,
        "extract_pdf_text",
        lambda _path: "We propose a local approach. Results show it improves recall.",
    )

    summary = ingest_papers.ingest_papers(
        str(papers_dir),
        str(db_path),
        extract_statements=True,
    )

    statements = get_statements(str(db_path), paper_id="paper-01")

    assert summary.statements == 2
    assert [statement["statement_type"] for statement in statements] == ["method", "result"]
    assert statements[0]["chunk_id"] == "paper-01:chunk_0000"


def test_ingest_filters_statements_and_reports_raw_and_saved_counts(tmp_path, monkeypatch, capsys):
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    (papers_dir / "paper-01.pdf").write_bytes(b"not a real pdf; extraction is mocked")
    db_path = tmp_path / "processed" / "papers.sqlite"

    monkeypatch.setattr(
        ingest_papers.pdf_tools,
        "extract_pdf_text",
        lambda _path: (
            "We propose a deterministic local graph construction approach for papers. "
            "We introduce a second deterministic graph quality method for papers. "
            "This sentence is long enough but has no useful extraction rule."
        ),
    )

    summary = ingest_papers.ingest_papers(
        str(papers_dir),
        str(db_path),
        extract_statements=True,
        filter_extracted_statements=True,
        max_statements_per_type_per_paper=1,
    )

    statements = get_statements(str(db_path), paper_id="paper-01")
    output = capsys.readouterr().out

    assert summary.raw_statements == 3
    assert summary.statements == 1
    assert len(statements) == 1
    assert statements[0]["statement_type"] == "method"
    assert "3 raw statements, 1 saved statements" in output


def test_ingest_rejects_missing_papers_directory(tmp_path):
    db_path = tmp_path / "processed" / "papers.sqlite"

    with pytest.raises(FileNotFoundError, match="Papers directory does not exist"):
        ingest_papers.ingest_papers(str(tmp_path / "missing"), str(db_path))


def test_cli_returns_error_for_missing_papers_directory(tmp_path, capsys):
    exit_code = ingest_papers.main(
        [
            "--papers-dir",
            str(tmp_path / "missing"),
            "--db-path",
            str(tmp_path / "processed" / "papers.sqlite"),
        ]
    )

    assert exit_code == 1
    assert "Papers directory does not exist" in capsys.readouterr().err


def test_direct_script_execution_can_import_local_tools(tmp_path):
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    db_path = tmp_path / "processed" / "papers.sqlite"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/ingest_papers.py",
            "--papers-dir",
            str(papers_dir),
            "--db-path",
            str(db_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Ingested 0 papers, 0 chunks, 0 statements, skipped 0 files." in result.stdout
    assert "ModuleNotFoundError" not in result.stderr
    assert db_path.exists()
