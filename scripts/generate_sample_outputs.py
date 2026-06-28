"""Generate compact sample outputs for reviewer-friendly documentation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


DEFAULT_OUTPUT_DIR = "docs/sample_outputs"
DEFAULT_BRIEF_PATH = "data/processed/researchnavigator_brief.md"
DEFAULT_EVALUATION_PATH = "data/processed/evaluation_report.json"
DEFAULT_GOLDEN_PATH = "data/processed/golden_eval_report.json"
DEFAULT_DISCOVERY_PATH = "data/processed/gaps_and_hypotheses.json"
MAX_TEXT_CHARS = 5000


def _resolve_local_path(path_value: str, label: str) -> Path:
    if not path_value or not path_value.strip():
        raise ValueError(f"{label} must be a non-empty local path.")
    parsed = urlparse(path_value)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError(f"{label} must be a local path.")
    return Path(parsed.path if parsed.scheme == "file" else path_value).expanduser()


def generate_sample_outputs(
    output_dir: str = DEFAULT_OUTPUT_DIR,
    brief_path: str = DEFAULT_BRIEF_PATH,
    evaluation_path: str = DEFAULT_EVALUATION_PATH,
    golden_path: str = DEFAULT_GOLDEN_PATH,
    discovery_path: str = DEFAULT_DISCOVERY_PATH,
) -> dict:
    """Write compact sample-output files derived from local processed artifacts."""

    output = _resolve_local_path(output_dir, "output_dir")
    output.mkdir(parents=True, exist_ok=True)

    brief = _read_text_excerpt(_resolve_local_path(brief_path, "brief_path"))
    evaluation = _read_json(_resolve_local_path(evaluation_path, "evaluation_path"))
    golden = _read_json(_resolve_local_path(golden_path, "golden_path"))
    discovery = _read_json(_resolve_local_path(discovery_path, "discovery_path"))

    files = {
        "researchnavigator_brief_excerpt.md": _write_text(
            output / "researchnavigator_brief_excerpt.md",
            brief,
        ),
        "evaluation_report_excerpt.json": _write_json(
            output / "evaluation_report_excerpt.json",
            _evaluation_excerpt(evaluation),
        ),
        "golden_eval_report_excerpt.json": _write_json(
            output / "golden_eval_report_excerpt.json",
            _golden_excerpt(golden),
        ),
        "top_discoveries_excerpt.json": _write_json(
            output / "top_discoveries_excerpt.json",
            _discovery_excerpt(discovery),
        ),
    }
    return {
        "output_dir": str(output),
        "files": files,
    }


def _read_text_excerpt(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Required sample source is missing: {path}")
    text = path.read_text(encoding="utf-8")
    if len(text) <= MAX_TEXT_CHARS:
        return text
    return text[: MAX_TEXT_CHARS - 4].rstrip() + "\n...\n"


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required sample source is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_text(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return str(path)


def _write_json(path: Path, payload: dict) -> str:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def _evaluation_excerpt(report: dict) -> dict:
    return {
        "overall_score": report.get("overall_score"),
        "grounding_score": report.get("grounding_score"),
        "safety_score": report.get("safety_score"),
        "testability_score": report.get("testability_score"),
        "traceability_score": report.get("traceability_score"),
        "total_gaps": report.get("total_gaps"),
        "total_hypotheses": report.get("total_hypotheses"),
        "total_experiment_plans": report.get("total_experiment_plans"),
        "warnings": report.get("warnings", [])[:5],
        "failed_checks": report.get("failed_checks", [])[:5],
        "metric_details": {
            "statement_count": report.get("metric_details", {}).get("statement_count"),
            "paper_count": report.get("metric_details", {}).get("paper_count"),
            "unique_evidence_statement_count": report.get("metric_details", {}).get(
                "unique_evidence_statement_count"
            ),
            "plan_specificity_score": report.get("metric_details", {}).get("plan_specificity_score"),
        },
    }


def _golden_excerpt(report: dict) -> dict:
    return {
        "total_cases": report.get("total_cases"),
        "passed_cases": report.get("passed_cases"),
        "failed_cases": report.get("failed_cases"),
        "pass_rate": report.get("pass_rate"),
        "case_results": [
            {
                "id": item.get("id"),
                "category": item.get("category"),
                "passed": item.get("passed"),
                "failed_checks": item.get("failed_checks", []),
            }
            for item in report.get("results", [])[:10]
        ],
    }


def _discovery_excerpt(payload: dict) -> dict:
    return {
        "counts": payload.get("counts", {}),
        "top_gaps": [
            {
                "gap_id": item.get("gap_id"),
                "gap_type": item.get("gap_type"),
                "gap_text": item.get("gap_text"),
                "source_statement_ids": item.get("source_statement_ids", []),
            }
            for item in payload.get("gaps", [])[:3]
        ],
        "top_hypotheses": [
            {
                "hypothesis_id": item.get("hypothesis_id"),
                "gap_id": item.get("gap_id"),
                "hypothesis_text": item.get("hypothesis_text"),
                "confidence_level": item.get("confidence_level"),
                "safety_label": item.get("safety_label"),
                "evidence_statement_ids": item.get("evidence_statement_ids", []),
            }
            for item in payload.get("hypotheses", [])[:3]
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate compact sample output docs.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--brief-path", default=DEFAULT_BRIEF_PATH)
    parser.add_argument("--evaluation-path", default=DEFAULT_EVALUATION_PATH)
    parser.add_argument("--golden-path", default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--discovery-path", default=DEFAULT_DISCOVERY_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = generate_sample_outputs(
            output_dir=args.output_dir,
            brief_path=args.brief_path,
            evaluation_path=args.evaluation_path,
            golden_path=args.golden_path,
            discovery_path=args.discovery_path,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Sample outputs: {result['output_dir']}")
    for label, path in result["files"].items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
