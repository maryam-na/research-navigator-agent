"""Run local preflight checks before a ResearchNavigator demo."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import networkx as nx

from app.schemas import (
    ChunkRecord,
    DiscoveryPayload,
    EvaluationReport,
    PaperRecord,
    StatementRecord,
)
from scripts.project_stats import calculate_project_stats
from tools.config_tools import load_config
from tools.logging_tools import log_error, log_info
from tools.storage_tools import get_chunks, get_papers, get_statements


REQUIRED_IMPORTS = [
    "google.adk",
    "streamlit",
    "pydantic",
    "networkx",
    "pypdf",
    "pandas",
]

REQUIRED_PROJECT_FILES = [
    "README.md",
    "pyproject.toml",
    "configs/default.yaml",
    "scripts/run_demo.py",
    "scripts/ingest_papers.py",
    "scripts/build_graph.py",
    "scripts/discover_gaps.py",
    "scripts/evaluate_outputs.py",
    "scripts/validate_submission.py",
    "ui/streamlit_app.py",
    "app/agent.py",
    "app/adk_tools.py",
    "app/schemas/__init__.py",
    "app/schemas/paper.py",
    "app/schemas/statement.py",
    "app/schemas/discovery.py",
    "app/schemas/evaluation.py",
]

PROCESSED_ARTIFACTS = [
    "data/processed/papers.sqlite",
    "data/processed/research_graph.graphml",
    "data/processed/gaps_and_hypotheses.json",
    "data/processed/evaluation_report.json",
]


def _resolve_local_path(path_value: str, label: str) -> Path:
    if not path_value or not path_value.strip():
        raise ValueError(f"{label} must be a non-empty local path.")
    parsed = urlparse(path_value)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError(f"{label} must be a local path.")
    return Path(parsed.path if parsed.scheme == "file" else path_value).expanduser()


def run_preflight(
    project_root: str = ".",
    require_artifacts: bool = False,
    required_imports: Iterable[str] = REQUIRED_IMPORTS,
    required_project_files: Iterable[str] = REQUIRED_PROJECT_FILES,
    processed_artifacts: Iterable[str] = PROCESSED_ARTIFACTS,
) -> dict[str, Any]:
    """Return deterministic local demo-readiness checks."""

    root = _resolve_local_path(project_root, "project_root")
    checks: list[dict[str, str]] = []
    checks.extend(_check_project_root(root))
    if not root.exists() or not root.is_dir():
        return _build_report(checks)

    checks.extend(_check_python_version())
    checks.extend(_check_imports(required_imports))
    checks.extend(_check_required_project_files(root, required_project_files))
    checks.extend(_check_config(root))
    checks.extend(_check_papers_dir(root))
    checks.extend(_check_processed_artifacts(root, require_artifacts, processed_artifacts))

    failed = [check for check in checks if check["status"] == "fail"]
    if not failed:
        checks.extend(_check_existing_outputs(root, processed_artifacts))
    return _build_report(checks)


def _check_project_root(root: Path) -> list[dict[str, str]]:
    return [
        _result(
            "environment",
            "project_root",
            "pass" if root.exists() and root.is_dir() else "fail",
            f"Project root found: {root}" if root.exists() and root.is_dir() else f"Project root is missing: {root}",
        )
    ]


def _check_python_version() -> list[dict[str, str]]:
    major, minor = sys.version_info[:2]
    return [
        _result(
            "environment",
            "python_version",
            "pass" if (major, minor) >= (3, 11) else "fail",
            f"Python {major}.{minor} detected; project requires Python 3.11+.",
        )
    ]


def _check_imports(required_imports: Iterable[str]) -> list[dict[str, str]]:
    checks = []
    for module_name in sorted(set(required_imports)):
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            checks.append(
                _result(
                    "dependency",
                    module_name,
                    "fail",
                    f"Import failed: {exc.__class__.__name__}: {exc}",
                )
            )
        else:
            checks.append(_result("dependency", module_name, "pass", "Import succeeded."))
    return checks


def _check_required_project_files(root: Path, required_project_files: Iterable[str]) -> list[dict[str, str]]:
    checks = []
    for relative_path in sorted(set(required_project_files)):
        file_path = root / relative_path
        checks.append(
            _result(
                "project_file",
                relative_path,
                "pass" if file_path.exists() and file_path.stat().st_size >= 0 else "fail",
                "Required file exists." if file_path.exists() else "Required file is missing.",
            )
        )
    return checks


def _check_config(root: Path) -> list[dict[str, str]]:
    config_path = root / "configs" / "default.yaml"
    if not config_path.exists():
        return [_result("config", "configs/default.yaml", "fail", "Default config is missing.")]
    try:
        config = load_config(config_path)
    except Exception as exc:
        return [_result("config", "configs/default.yaml", "fail", f"Config invalid: {exc}")]
    return [
        _result(
            "config",
            "configs/default.yaml",
            "pass",
            f"Config version {config.version} loaded.",
        )
    ]


def _check_papers_dir(root: Path) -> list[dict[str, str]]:
    papers_dir = root / "data" / "papers"
    if not papers_dir.exists():
        return [_result("input_data", "data/papers", "warn", "Paper directory is missing; run demo after adding 5-10 local PDFs.")]
    pdf_count = len(sorted(papers_dir.glob("*.pdf")))
    status = "pass" if 5 <= pdf_count <= 10 else "warn"
    return [
        _result(
            "input_data",
            "data/papers",
            status,
            f"Found {pdf_count} local PDFs; recommended MVP range is 5-10.",
        )
    ]


def _check_processed_artifacts(
    root: Path,
    require_artifacts: bool,
    processed_artifacts: Iterable[str],
) -> list[dict[str, str]]:
    checks = []
    missing_status = "fail" if require_artifacts else "warn"
    missing_message = (
        "Required processed artifact is missing."
        if require_artifacts
        else "Processed artifact is missing; run `make demo` to generate it."
    )
    for relative_path in sorted(set(processed_artifacts)):
        file_path = root / relative_path
        exists = file_path.exists() and file_path.stat().st_size > 0
        checks.append(
            _result(
                "processed_artifact",
                relative_path,
                "pass" if exists else missing_status,
                "Processed artifact exists." if exists else missing_message,
            )
        )
    return checks


def _check_existing_outputs(root: Path, processed_artifacts: Iterable[str]) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    artifacts = set(processed_artifacts)
    if "data/processed/papers.sqlite" in artifacts:
        checks.extend(_check_database(root / "data" / "processed" / "papers.sqlite"))
    if "data/processed/research_graph.graphml" in artifacts:
        checks.extend(_check_graph(root / "data" / "processed" / "research_graph.graphml"))
    if "data/processed/gaps_and_hypotheses.json" in artifacts:
        checks.extend(_check_discovery_payload(root / "data" / "processed" / "gaps_and_hypotheses.json"))
    if "data/processed/evaluation_report.json" in artifacts:
        checks.extend(_check_evaluation_report(root / "data" / "processed" / "evaluation_report.json"))
    return checks


def _check_database(db_path: Path) -> list[dict[str, str]]:
    if not db_path.exists():
        return []
    try:
        papers = get_papers(str(db_path))
        chunks = get_chunks(str(db_path))
        statements = get_statements(str(db_path))
        for paper in papers[:5]:
            PaperRecord.model_validate(paper)
        for chunk in chunks[:5]:
            ChunkRecord.model_validate(chunk)
        for statement in statements[:5]:
            StatementRecord.model_validate(statement)
        stats = calculate_project_stats(str(db_path))
    except Exception as exc:
        return [_result("database", "data/processed/papers.sqlite", "fail", f"SQLite output invalid: {exc}")]

    return [
        _result("database", "papers", "pass" if papers else "warn", f"Papers stored: {len(papers)}."),
        _result("database", "chunks", "pass" if chunks else "warn", f"Chunks stored: {len(chunks)}."),
        _result(
            "database",
            "statements",
            "pass" if statements else "warn",
            f"Statements stored: {len(statements)}.",
        ),
        _result(
            "performance",
            "graph_size",
            "pass" if int(stats["graph_nodes"]) <= 3000 else "warn",
            f"Graph nodes from current statements: {stats['graph_nodes']}.",
        ),
    ]


def _check_graph(graph_path: Path) -> list[dict[str, str]]:
    if not graph_path.exists():
        return []
    try:
        graph = nx.read_graphml(graph_path)
    except Exception as exc:
        return [_result("graph", "data/processed/research_graph.graphml", "fail", f"GraphML invalid: {exc}")]
    return [
        _result("graph", "nodes", "pass" if graph.number_of_nodes() > 0 else "warn", f"Nodes: {graph.number_of_nodes()}."),
        _result("graph", "edges", "pass" if graph.number_of_edges() > 0 else "warn", f"Edges: {graph.number_of_edges()}."),
    ]


def _check_discovery_payload(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        discovery = DiscoveryPayload.model_validate(payload)
    except Exception as exc:
        return [_result("schema", "data/processed/gaps_and_hypotheses.json", "fail", f"Discovery payload invalid: {exc}")]

    counts_match = (
        discovery.counts.gaps == len(discovery.gaps)
        and discovery.counts.hypotheses == len(discovery.hypotheses)
        and discovery.counts.experiment_plans == len(discovery.experiment_plans)
    )
    return [
        _result(
            "schema",
            "data/processed/gaps_and_hypotheses.json",
            "pass" if counts_match else "fail",
            "Discovery counts match payload lengths." if counts_match else "Discovery counts do not match payload lengths.",
        )
    ]


def _check_evaluation_report(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        report = EvaluationReport.model_validate(payload)
    except Exception as exc:
        return [_result("schema", "data/processed/evaluation_report.json", "fail", f"Evaluation report invalid: {exc}")]

    return [
        _result(
            "evaluation",
            "failed_checks",
            "pass" if not report.failed_checks else "fail",
            f"Failed evaluation checks: {len(report.failed_checks)}.",
        ),
        _result(
            "evaluation",
            "overall_score",
            "pass" if report.overall_score >= 0.75 else "warn",
            f"Overall score: {report.overall_score}.",
        ),
    ]


def _build_report(checks: list[dict[str, str]]) -> dict[str, Any]:
    failed = [check for check in checks if check["status"] == "fail"]
    warnings = [check for check in checks if check["status"] == "warn"]
    passed = [check for check in checks if check["status"] == "pass"]
    return {
        "ready": not failed,
        "summary": {
            "passed": len(passed),
            "warnings": len(warnings),
            "failed": len(failed),
            "total": len(checks),
        },
        "next_command": _next_command(checks),
        "checks": checks,
    }


def _next_command(checks: list[dict[str, str]]) -> str:
    failed = [check for check in checks if check["status"] == "fail"]
    if failed:
        return "Fix failed preflight checks, then rerun `make preflight`."
    missing_artifacts = [
        check
        for check in checks
        if check["category"] == "processed_artifact" and check["status"] == "warn"
    ]
    if missing_artifacts:
        return "make demo"
    return "make validate && make ui"


def _result(category: str, name: str, status: str, message: str) -> dict[str, str]:
    return {
        "category": category,
        "name": name,
        "status": status,
        "message": message,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local preflight checks before the demo.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--require-artifacts", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print the full preflight report as JSON.")
    parser.add_argument(
        "--output-path",
        default="data/processed/preflight_report.json",
        help="Where to write the JSON preflight report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = run_preflight(args.project_root, require_artifacts=args.require_artifacts)
        output_path = _resolve_local_path(args.output_path, "output_path")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        log_error("preflight.failed", str(exc))
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        log_info(
            "preflight.completed",
            ready=report["ready"],
            passed=summary["passed"],
            warnings=summary["warnings"],
            failed=summary["failed"],
            next_command=report["next_command"],
            report=args.output_path,
        )
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
