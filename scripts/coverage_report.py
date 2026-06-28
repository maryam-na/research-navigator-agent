"""Generate local pytest coverage reports for ResearchNavigator."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.logging_tools import log_error, log_info


COVERAGE_SOURCES = ("app", "tools", "scripts", "ui")
DEFAULT_JSON_PATH = "data/processed/coverage.json"
DEFAULT_MARKDOWN_PATH = "data/processed/coverage_summary.md"


def _resolve_local_path(path_value: str, label: str) -> Path:
    if not path_value or not path_value.strip():
        raise ValueError(f"{label} must be a non-empty local path.")
    parsed = urlparse(path_value)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError(f"{label} must be a local path.")
    return Path(parsed.path if parsed.scheme == "file" else path_value).expanduser()


def run_pytest_coverage(
    json_path: str = DEFAULT_JSON_PATH,
    extra_pytest_args: list[str] | None = None,
) -> int:
    """Run pytest with coverage and write a coverage JSON report."""

    output_path = _resolve_local_path(json_path, "json_path")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pytest",
        *[f"--cov={source}" for source in COVERAGE_SOURCES],
        "--cov-report=term-missing",
        f"--cov-report=json:{output_path}",
        *(extra_pytest_args or []),
    ]
    completed = subprocess.run(command, check=False)
    return completed.returncode


def summarize_coverage_json(json_path: str = DEFAULT_JSON_PATH, lowest_file_count: int = 10) -> dict[str, Any]:
    """Summarize a coverage.py JSON report deterministically."""

    if lowest_file_count <= 0:
        raise ValueError("lowest_file_count must be greater than 0.")
    path = _resolve_local_path(json_path, "json_path")
    if not path.exists():
        raise FileNotFoundError(f"Coverage JSON report does not exist: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    totals = payload.get("totals", {})
    files = payload.get("files", {})
    file_summaries = []
    for filename, details in files.items():
        summary = details.get("summary", {})
        file_summaries.append(
            {
                "file": filename,
                "percent_covered": round(float(summary.get("percent_covered", 0.0)), 2),
                "num_statements": int(summary.get("num_statements", 0)),
                "missing_lines": int(summary.get("missing_lines", 0)),
                "excluded_lines": int(summary.get("excluded_lines", 0)),
            }
        )
    lowest_files = sorted(
        file_summaries,
        key=lambda item: (item["percent_covered"], item["file"]),
    )[:lowest_file_count]
    return {
        "total_percent_covered": round(float(totals.get("percent_covered", 0.0)), 2),
        "covered_lines": int(totals.get("covered_lines", 0)),
        "num_statements": int(totals.get("num_statements", 0)),
        "missing_lines": int(totals.get("missing_lines", 0)),
        "excluded_lines": int(totals.get("excluded_lines", 0)),
        "file_count": len(file_summaries),
        "lowest_coverage_files": lowest_files,
    }


def build_markdown_summary(summary: dict[str, Any], min_total: float = 0.0) -> str:
    """Build a judge-friendly Markdown coverage summary."""

    total = float(summary["total_percent_covered"])
    status = "pass" if total >= min_total else "below threshold"
    lines = [
        "# Coverage Summary",
        "",
        "Generated locally with `pytest-cov`.",
        "",
        f"- Status: `{status}`",
        f"- Total coverage: `{total:.2f}%`",
        f"- Minimum threshold: `{min_total:.2f}%`",
        f"- Covered lines: `{summary['covered_lines']}`",
        f"- Missing lines: `{summary['missing_lines']}`",
        f"- Statements: `{summary['num_statements']}`",
        f"- Files measured: `{summary['file_count']}`",
        "",
        "## Lowest Coverage Files",
        "",
        "| File | Coverage | Statements | Missing Lines |",
        "| --- | ---: | ---: | ---: |",
    ]
    for item in summary["lowest_coverage_files"]:
        lines.append(
            f"| `{item['file']}` | {item['percent_covered']:.2f}% | "
            f"{item['num_statements']} | {item['missing_lines']} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Coverage is a quality signal, not a scientific validity score.",
            "- Deterministic safety, grounding, golden-case, and submission checks remain separate.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_coverage_summary(
    json_path: str = DEFAULT_JSON_PATH,
    markdown_path: str = DEFAULT_MARKDOWN_PATH,
    min_total: float = 0.0,
) -> dict[str, Any]:
    """Read coverage JSON, write Markdown summary, and return compact metrics."""

    summary = summarize_coverage_json(json_path)
    output_path = _resolve_local_path(markdown_path, "markdown_path")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_markdown_summary(summary, min_total=min_total), encoding="utf-8")
    return {
        "ready": summary["total_percent_covered"] >= min_total,
        "min_total": min_total,
        "json_path": json_path,
        "markdown_path": markdown_path,
        **summary,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run pytest coverage and write local reports.")
    parser.add_argument("--json-path", default=DEFAULT_JSON_PATH)
    parser.add_argument("--markdown-path", default=DEFAULT_MARKDOWN_PATH)
    parser.add_argument("--min-total", type=float, default=0.0)
    parser.add_argument("--skip-pytest", action="store_true", help="Summarize an existing coverage JSON file.")
    parser.add_argument("--json", action="store_true", help="Print compact coverage metrics as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.min_total < 0 or args.min_total > 100:
            raise ValueError("--min-total must be between 0 and 100.")
        if not args.skip_pytest:
            pytest_code = run_pytest_coverage(args.json_path)
            if pytest_code != 0:
                return pytest_code
        report = write_coverage_summary(args.json_path, args.markdown_path, args.min_total)
    except Exception as exc:
        log_error("coverage_report.failed", str(exc))
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        log_info(
            "coverage_report.completed",
            ready=report["ready"],
            total_percent=report["total_percent_covered"],
            min_total=report["min_total"],
            report=args.markdown_path,
            json_report=args.json_path,
        )
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
