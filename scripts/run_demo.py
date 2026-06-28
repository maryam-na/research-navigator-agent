"""Run the full local ResearchNavigator demo pipeline."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_graph import build_graph_from_database
from scripts.discover_gaps import discover_from_database
from scripts.evaluate_outputs import evaluate_from_files
from scripts.ingest_papers import ingest_papers
from tools.config_tools import load_config
from tools.logging_tools import log_error, log_info
from ui.data_access import create_research_brief, load_processed_data

ProgressCallback = Callable[[str, str], None]


def _notify_progress(
    progress_callback: ProgressCallback | None,
    stage: str,
    message: str,
) -> None:
    if progress_callback is not None:
        progress_callback(stage, message)


def _resolve_local_path(path_value: str, label: str) -> Path:
    if not path_value or not path_value.strip():
        raise ValueError(f"{label} must be a non-empty local path.")
    parsed = urlparse(path_value)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError(f"{label} must be a local path.")
    return Path(parsed.path if parsed.scheme == "file" else path_value).expanduser()


def run_demo(
    papers_dir: str = "data/papers",
    db_path: str = "data/processed/papers.sqlite",
    graph_path: str = "data/processed/research_graph.graphml",
    discovery_path: str = "data/processed/gaps_and_hypotheses.json",
    evaluation_path: str = "data/processed/evaluation_report.json",
    brief_path: str = "data/processed/researchnavigator_brief.md",
    max_statements_per_type_per_paper: int = 30,
    max_gaps: int = 10,
    max_hypotheses: int = 10,
    reset: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    """Run ingestion, graph building, gap discovery, and evaluation."""

    if max_statements_per_type_per_paper <= 0:
        raise ValueError("max_statements_per_type_per_paper must be greater than 0.")

    output_paths = [
        _resolve_local_path(db_path, "db_path"),
        _resolve_local_path(graph_path, "graph_path"),
        _resolve_local_path(discovery_path, "discovery_path"),
        _resolve_local_path(evaluation_path, "evaluation_path"),
    ]
    if reset:
        _notify_progress(
            progress_callback,
            "reset_started",
            "Removing existing processed artifacts before the local pipeline run.",
        )
        log_info("demo.reset_started", "Removing existing processed outputs.")
        for path in output_paths:
            if path.exists() and path.is_file():
                path.unlink()

    _notify_progress(progress_callback, "ingest_started", "Ingesting local PDFs into SQLite.")
    log_info("demo.ingest_started", papers_dir=papers_dir, db_path=db_path)
    ingestion = ingest_papers(
        papers_dir,
        db_path,
        extract_statements=True,
        filter_extracted_statements=True,
        max_statements_per_type_per_paper=max_statements_per_type_per_paper,
    )
    log_info(
        "demo.ingest_completed",
        papers=ingestion.papers,
        chunks=ingestion.chunks,
        raw_statements=ingestion.raw_statements,
        saved_statements=ingestion.statements,
        skipped_files=ingestion.skipped_files,
    )
    _notify_progress(
        progress_callback,
        "graph_started",
        "Building the local NetworkX knowledge graph.",
    )
    log_info("demo.graph_started", graph_path=graph_path)
    graph_summary = build_graph_from_database(db_path, graph_path)
    log_info(
        "demo.graph_completed",
        nodes=graph_summary.get("nodes"),
        edges=graph_summary.get("edges"),
        exported=graph_summary.get("exported"),
    )
    _notify_progress(
        progress_callback,
        "discovery_started",
        "Finding grounded gaps and speculative hypotheses.",
    )
    log_info("demo.discovery_started", max_gaps=max_gaps, max_hypotheses=max_hypotheses)
    discovery = discover_from_database(
        db_path,
        discovery_path,
        max_gaps=max_gaps,
        max_hypotheses=max_hypotheses,
    )
    log_info(
        "demo.discovery_completed",
        gaps=discovery["counts"].get("gaps"),
        hypotheses=discovery["counts"].get("hypotheses"),
        experiment_plans=discovery["counts"].get("experiment_plans"),
    )
    _notify_progress(
        progress_callback,
        "evaluation_started",
        "Evaluating grounding, safety, testability, and traceability.",
    )
    log_info("demo.evaluation_started", output_path=evaluation_path)
    evaluation = evaluate_from_files(db_path, discovery_path, evaluation_path)
    log_info(
        "demo.evaluation_completed",
        overall_score=evaluation.get("overall_score"),
        warnings=len(evaluation.get("warnings", [])),
        failed_checks=len(evaluation.get("failed_checks", [])),
    )
    _notify_progress(
        progress_callback,
        "brief_started",
        "Writing the local Markdown research brief.",
    )
    processed_data = load_processed_data(
        db_path,
        gaps_path=discovery_path,
        evaluation_path=evaluation_path,
        graph_path=graph_path,
    )
    brief_output = _resolve_local_path(brief_path, "brief_path")
    brief_output.parent.mkdir(parents=True, exist_ok=True)
    brief_output.write_text(create_research_brief(processed_data), encoding="utf-8")
    log_info("demo.brief_written", brief_path=str(brief_output))
    _notify_progress(progress_callback, "completed", "Local pipeline completed.")
    return {
        "papers": ingestion.papers,
        "chunks": ingestion.chunks,
        "raw_statements": ingestion.raw_statements,
        "saved_statements": ingestion.statements,
        "skipped_files": ingestion.skipped_files,
        "graph": graph_summary,
        "discovery_counts": discovery["counts"],
        "evaluation": {
            "overall_score": evaluation.get("overall_score"),
            "grounding_score": evaluation.get("grounding_score"),
            "safety_score": evaluation.get("safety_score"),
            "testability_score": evaluation.get("testability_score"),
            "traceability_score": evaluation.get("traceability_score"),
            "warnings": len(evaluation.get("warnings", [])),
            "failed_checks": len(evaluation.get("failed_checks", [])),
        },
        "brief_path": str(brief_output),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local ResearchNavigator demo pipeline.")
    parser.add_argument("--papers-dir", default=None)
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--graph-path", default=None)
    parser.add_argument("--discovery-path", default=None)
    parser.add_argument("--evaluation-path", default=None)
    parser.add_argument("--brief-path", default=None)
    parser.add_argument("--max-statements-per-type-per-paper", type=int, default=None)
    parser.add_argument("--max-gaps", type=int, default=None)
    parser.add_argument("--max-hypotheses", type=int, default=None)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove existing processed outputs first.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config()
    try:
        summary = run_demo(
            papers_dir=args.papers_dir or config.paths.papers_dir,
            db_path=args.db_path or config.paths.db_path,
            graph_path=args.graph_path or config.paths.graph_path,
            discovery_path=args.discovery_path or config.paths.discovery_path,
            evaluation_path=args.evaluation_path or config.paths.evaluation_path,
            brief_path=args.brief_path or config.paths.brief_path,
            max_statements_per_type_per_paper=(
                args.max_statements_per_type_per_paper
                or config.pipeline.max_statements_per_type_per_paper
            ),
            max_gaps=args.max_gaps or config.pipeline.max_gaps,
            max_hypotheses=args.max_hypotheses or config.pipeline.max_hypotheses,
            reset=args.reset,
        )
    except Exception as exc:
        log_error("demo.failed", str(exc))
        return 1

    log_info(
        "demo.completed",
        "ResearchNavigator demo complete.",
        papers=summary["papers"],
        chunks=summary["chunks"],
        saved_statements=summary["saved_statements"],
        raw_statements=summary["raw_statements"],
        graph_nodes=summary["graph"]["nodes"],
        graph_edges=summary["graph"]["edges"],
        gaps=summary["discovery_counts"]["gaps"],
        hypotheses=summary["discovery_counts"]["hypotheses"],
        overall_score=summary["evaluation"]["overall_score"],
        warnings=summary["evaluation"]["warnings"],
        failed_checks=summary["evaluation"]["failed_checks"],
        brief=summary["brief_path"],
    )
    log_info(
        "demo.next_step",
        "Open the dashboard.",
        command="uv run streamlit run ui/streamlit_app.py",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
