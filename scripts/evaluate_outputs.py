"""Evaluate generated gaps, hypotheses, and experiment plans locally."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.evaluation_tools import evaluate_outputs
from tools.storage_tools import get_statements


def _resolve_local_path(path_value: str, label: str) -> Path:
    if not path_value or not path_value.strip():
        raise ValueError(f"{label} must be a non-empty local path.")
    parsed = urlparse(path_value)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError(f"{label} must be a local path.")
    return Path(parsed.path if parsed.scheme == "file" else path_value).expanduser()


def evaluate_from_files(db_path: str, input_path: str, output_path: str) -> dict:
    statements = get_statements(db_path)
    input_file = _resolve_local_path(input_path, "input_path")
    if not input_file.exists():
        raise FileNotFoundError(f"Input JSON does not exist: {input_file}")
    payload = json.loads(input_file.read_text(encoding="utf-8"))
    report = evaluate_outputs(
        payload.get("gaps", []),
        payload.get("hypotheses", []),
        payload.get("experiment_plans", []),
        statements,
    )
    output_file = _resolve_local_path(output_path, "output_path")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate local research gaps, hypotheses, and experiment plans.",
    )
    parser.add_argument(
        "--db-path",
        default="data/processed/papers.sqlite",
        help="SQLite database path containing extracted statements.",
    )
    parser.add_argument(
        "--input-path",
        default="data/processed/gaps_and_hypotheses.json",
        help="Input JSON from scripts/discover_gaps.py.",
    )
    parser.add_argument(
        "--output-path",
        default="data/processed/evaluation_report.json",
        help="Output evaluation report JSON path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        report = evaluate_from_files(args.db_path, args.input_path, args.output_path)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Overall score: {report['overall_score']}")
    print(f"Grounding score: {report['grounding_score']}")
    print(f"Safety score: {report['safety_score']}")
    print(f"Testability score: {report['testability_score']}")
    print(f"Traceability score: {report['traceability_score']}")
    print(f"Warnings: {len(report.get('warnings', []))}")
    print(f"Failed checks: {len(report['failed_checks'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
