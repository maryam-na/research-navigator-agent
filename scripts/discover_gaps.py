"""Discover deterministic research gaps and hypotheses from stored statements."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.gap_tools import discover_research_gaps, generate_experiment_plan, generate_hypotheses
from tools.storage_tools import get_statements


def _resolve_local_output_path(path_value: str) -> Path:
    if not path_value or not path_value.strip():
        raise ValueError("output_path must be a non-empty local file path.")
    parsed = urlparse(path_value)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError("Only local JSON output paths are supported.")
    path = Path(parsed.path if parsed.scheme == "file" else path_value).expanduser()
    if path.exists() and path.is_dir():
        raise ValueError(f"Output path points to a directory: {path}")
    return path


def discover_from_database(
    db_path: str,
    output_path: str,
    max_gaps: int = 10,
    max_hypotheses: int = 10,
) -> dict:
    statements = get_statements(db_path)
    gaps = discover_research_gaps(statements, max_gaps=max_gaps)
    hypotheses = generate_hypotheses(gaps, statements, max_hypotheses=max_hypotheses)
    experiment_plans = [
        {
            "hypothesis_id": hypothesis["hypothesis_id"],
            "plan": generate_experiment_plan(hypothesis),
        }
        for hypothesis in hypotheses
    ]
    payload = {
        "counts": {
            "statements": len(statements),
            "gaps": len(gaps),
            "hypotheses": len(hypotheses),
            "experiment_plans": len(experiment_plans),
        },
        "gaps": gaps,
        "hypotheses": hypotheses,
        "experiment_plans": experiment_plans,
    }

    path = _resolve_local_output_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover local research gaps, hypotheses, and experiment plans.",
    )
    parser.add_argument(
        "--db-path",
        default="data/processed/papers.sqlite",
        help="SQLite database path containing extracted statements.",
    )
    parser.add_argument(
        "--output-path",
        default="data/processed/gaps_and_hypotheses.json",
        help="Output JSON path.",
    )
    parser.add_argument("--max-gaps", type=int, default=10, help="Maximum gaps to emit.")
    parser.add_argument(
        "--max-hypotheses",
        type=int,
        default=10,
        help="Maximum hypotheses to emit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        payload = discover_from_database(
            args.db_path,
            args.output_path,
            max_gaps=args.max_gaps,
            max_hypotheses=args.max_hypotheses,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    counts = payload["counts"]
    print(f"Statements: {counts['statements']}")
    print(f"Gaps: {counts['gaps']}")
    print(f"Hypotheses: {counts['hypotheses']}")
    print(f"Experiment plans: {counts['experiment_plans']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

