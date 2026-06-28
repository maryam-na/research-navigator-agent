"""Ingest local PDFs into SQLite as papers and deterministic text chunks."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.extraction_tools import deduplicate_statements, extract_research_statements, filter_statements
from tools import pdf_tools
from tools.storage_tools import initialize_database, save_chunk, save_paper, save_statement


@dataclass(frozen=True)
class IngestionSummary:
    papers: int
    chunks: int
    skipped_files: int
    statements: int = 0
    raw_statements: int = 0


def _resolve_local_path(path_value: str, label: str) -> Path:
    if not path_value or not path_value.strip():
        raise ValueError(f"{label} must be a non-empty local path.")

    parsed = urlparse(path_value)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError(f"{label} must be a local path.")

    return Path(parsed.path if parsed.scheme == "file" else path_value).expanduser()


def _paper_id_from_path(pdf_path: Path) -> str:
    return pdf_path.stem.strip().lower().replace(" ", "-")


def _title_from_path(pdf_path: Path) -> str:
    title = pdf_path.stem.replace("_", " ").replace("-", " ").strip()
    return title or pdf_path.stem


def ingest_papers(
    papers_dir: str,
    db_path: str,
    extract_statements: bool = False,
    filter_extracted_statements: bool = False,
    max_statements_per_type_per_paper: int = 50,
    include_unknown_statements: bool = False,
) -> IngestionSummary:
    """Read local PDFs from `papers_dir`, chunk them, and save to SQLite."""

    papers_path = _resolve_local_path(papers_dir, "papers_dir")
    database_path = _resolve_local_path(db_path, "db_path")

    if not papers_path.exists():
        raise FileNotFoundError(f"Papers directory does not exist: {papers_path}")
    if not papers_path.is_dir():
        raise ValueError(f"papers_dir must be a directory: {papers_path}")

    database_path.parent.mkdir(parents=True, exist_ok=True)
    initialize_database(str(database_path))

    papers_saved = 0
    chunks_saved = 0
    skipped_files = 0
    statements_saved = 0
    raw_statements = 0

    for pdf_path in sorted(papers_path.glob("*.pdf")):
        try:
            text = pdf_tools.extract_pdf_text(str(pdf_path))
            chunks = pdf_tools.chunk_text(text)
            if not chunks:
                skipped_files += 1
                print(f"Skipped {pdf_path.name}: no extractable text.")
                continue

            paper_id = _paper_id_from_path(pdf_path)
            save_paper(
                str(database_path),
                paper_id=paper_id,
                title=_title_from_path(pdf_path),
                source_path=str(pdf_path),
                license_notes="local input; verify open-access or synthetic status before use",
            )

            paper_statements: list[dict] = []
            for chunk_index, chunk in enumerate(chunks):
                saved_chunk_id = f"{paper_id}:{chunk['chunk_id']}"
                save_chunk(
                    str(database_path),
                    paper_id=paper_id,
                    chunk_id=saved_chunk_id,
                    chunk_index=chunk_index,
                    text=chunk["text"],
                    start_char=chunk["start_char"],
                    end_char=chunk["end_char"],
                )
                if extract_statements:
                    statements = extract_research_statements(
                        chunk["text"],
                        paper_id=paper_id,
                        chunk_id=saved_chunk_id,
                    )
                    raw_statements += len(statements)
                    paper_statements.extend(statements)

            if extract_statements:
                statements_to_save = deduplicate_statements(paper_statements)
                if filter_extracted_statements:
                    statements_to_save = filter_statements(
                        statements_to_save,
                        include_unknown=include_unknown_statements,
                        max_per_type_per_paper=max_statements_per_type_per_paper,
                    )
                for statement in statements_to_save:
                    save_statement(str(database_path), **statement)
                statements_saved += len(statements_to_save)

            papers_saved += 1
            chunks_saved += len(chunks)
        except Exception as exc:
            skipped_files += 1
            print(f"Skipped {pdf_path.name}: {exc}")

    summary = IngestionSummary(
        papers=papers_saved,
        chunks=chunks_saved,
        skipped_files=skipped_files,
        statements=statements_saved,
        raw_statements=raw_statements,
    )
    if extract_statements and filter_extracted_statements:
        print(
            "Ingested "
            f"{summary.papers} papers, {summary.chunks} chunks, "
            f"{summary.raw_statements} raw statements, "
            f"{summary.statements} saved statements, "
            f"skipped {summary.skipped_files} files."
        )
    else:
        print(
            "Ingested "
            f"{summary.papers} papers, {summary.chunks} chunks, "
            f"{summary.statements} statements, skipped {summary.skipped_files} files."
        )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest local PDF papers into a SQLite database.",
    )
    parser.add_argument("--papers-dir", default="data/papers", help="Directory containing local PDFs.")
    parser.add_argument(
        "--db-path",
        default="data/processed/papers.sqlite",
        help="SQLite database path for processed papers and chunks.",
    )
    parser.add_argument(
        "--extract-statements",
        action="store_true",
        help="Extract and save deterministic rule-based statements from each chunk.",
    )
    parser.add_argument(
        "--filter-statements",
        action="store_true",
        help="Filter extracted statements before saving them.",
    )
    parser.add_argument(
        "--max-statements-per-type-per-paper",
        type=int,
        default=50,
        help="Maximum saved statements per statement type per paper when filtering.",
    )
    parser.add_argument(
        "--include-unknown-statements",
        action="store_true",
        help="Include unknown statements when filtering extracted statements.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        ingest_papers(
            args.papers_dir,
            args.db_path,
            extract_statements=args.extract_statements,
            filter_extracted_statements=args.filter_statements,
            max_statements_per_type_per_paper=args.max_statements_per_type_per_paper,
            include_unknown_statements=args.include_unknown_statements,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
