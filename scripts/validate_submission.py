"""Validate that ResearchNavigator is ready for a local competition submission."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.project_stats import calculate_project_stats
from tools.config_tools import load_config
from tools.logging_tools import log_error, log_info

REQUIRED_FILES = [
    "README.md",
    "SUBMISSION.md",
    "CHANGELOG.md",
    "configs/default.yaml",
    "SKILL.md",
    "AGENTS.md",
    ".agent/skills/research-navigator/SKILL.md",
    "specs/project_spec.md",
    "specs/safety_policy.md",
    "specs/evaluation_plan.md",
    "specs/behavior_scenarios.md",
    "specs/policies.yaml",
    "evals/golden_cases.json",
    "docs/kaggle_submission_package.md",
    "docs/kaggle_video_script.md",
    "docs/capstone_evaluation_mapping.md",
    "docs/agent_technology_story.md",
    "docs/mcp_server.md",
    "docs/antigravity_demo_notes.md",
    "docs/demo_script.md",
    "docs/system_card.md",
    "docs/reproducibility.md",
    "docs/judge_walkthrough.md",
    "docs/security_review.md",
    "docs/dependency_audit.md",
    "docs/coverage_report.md",
    "app/agent.py",
    "app/adk_tools.py",
    "app/mcp_server.py",
    "app/schemas/__init__.py",
    "app/schemas/paper.py",
    "app/schemas/statement.py",
    "app/schemas/discovery.py",
    "app/schemas/evaluation.py",
    "scripts/coverage_report.py",
    "scripts/dependency_audit.py",
    "scripts/preflight.py",
    "scripts/run_mcp_server.py",
    "ui/streamlit_app.py",
    "Makefile",
    ".github/workflows/ci.yml",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/pull_request_template.md",
]

PROCESSED_FILES = [
    "data/processed/papers.sqlite",
    "data/processed/research_graph.graphml",
    "data/processed/gaps_and_hypotheses.json",
    "data/processed/evaluation_report.json",
    "data/processed/golden_eval_report.json",
    "data/processed/researchnavigator_brief.md",
]

SCREENSHOT_FILES = [
    "docs/screenshots/search.png",
    "docs/screenshots/evidence_inspector.png",
    "docs/screenshots/discoveries.png",
    "docs/screenshots/graph.png",
    "docs/screenshots/safety_evaluation.png",
]

SAMPLE_OUTPUT_FILES = [
    "docs/sample_outputs/researchnavigator_brief_excerpt.md",
    "docs/sample_outputs/evaluation_report_excerpt.json",
    "docs/sample_outputs/golden_eval_report_excerpt.json",
    "docs/sample_outputs/top_discoveries_excerpt.json",
]


def _resolve_local_path(path_value: str, label: str) -> Path:
    if not path_value or not path_value.strip():
        raise ValueError(f"{label} must be a non-empty local path.")
    parsed = urlparse(path_value)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError(f"{label} must be a local path.")
    return Path(parsed.path if parsed.scheme == "file" else path_value).expanduser()


def validate_submission(
    project_root: str = ".",
    min_overall_score: float = 0.75,
    min_golden_pass_rate: float = 1.0,
) -> dict:
    """Return a deterministic submission-readiness report."""

    root = _resolve_local_path(project_root, "project_root")
    if not root.exists() or not root.is_dir():
        raise ValueError(f"project_root must be an existing directory: {root}")

    checks: list[dict] = []
    checks.extend(_check_required_files(root))
    checks.extend(_check_config(root))
    checks.extend(_check_processed_files(root))
    checks.extend(_check_screenshot_files(root))
    checks.extend(_check_sample_output_files(root))
    checks.extend(_check_paper_manifest(root))
    checks.extend(_check_evaluation_report(root, min_overall_score))
    checks.extend(_check_golden_report(root, min_golden_pass_rate))
    checks.extend(_check_project_stats(root))
    checks.extend(_check_docs_content(root))

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
        "checks": checks,
    }


def _check_required_files(root: Path) -> list[dict]:
    return [
        _result(
            "required_file",
            str(path),
            "pass" if (root / path).exists() else "fail",
            "Required project file exists." if (root / path).exists() else "Required project file is missing.",
        )
        for path in REQUIRED_FILES
    ]


def _check_config(root: Path) -> list[dict]:
    config_path = root / "configs" / "default.yaml"
    if not config_path.exists():
        return [_result("config", "configs/default.yaml", "fail", "Default config is missing.")]
    try:
        config = load_config(config_path)
    except Exception as exc:
        return [_result("config", "configs/default.yaml", "fail", f"Config is invalid: {exc}")]
    return [
        _result(
            "config",
            "configs/default.yaml",
            "pass",
            f"Config version {config.version} loaded.",
        )
    ]


def _check_processed_files(root: Path) -> list[dict]:
    checks = []
    for path in PROCESSED_FILES:
        file_path = root / path
        exists = file_path.exists() and file_path.stat().st_size > 0
        checks.append(
            _result(
                "processed_artifact",
                path,
                "pass" if exists else "fail",
                "Processed artifact exists." if exists else "Run `make demo` and `make eval` to regenerate artifacts.",
            )
        )
    return checks


def _check_screenshot_files(root: Path) -> list[dict]:
    checks = []
    for path in SCREENSHOT_FILES:
        file_path = root / path
        exists = file_path.exists() and file_path.stat().st_size > 0
        checks.append(
            _result(
                "demo_screenshot",
                path,
                "pass" if exists else "warn",
                "Demo screenshot exists." if exists else "Add screenshot before final submission.",
            )
        )
    return checks


def _check_sample_output_files(root: Path) -> list[dict]:
    checks = []
    for path in SAMPLE_OUTPUT_FILES:
        file_path = root / path
        exists = file_path.exists() and file_path.stat().st_size > 0
        checks.append(
            _result(
                "sample_output",
                path,
                "pass" if exists else "warn",
                "Sample output exists." if exists else "Run `make samples` before final submission.",
            )
        )
    return checks


def _check_paper_manifest(root: Path) -> list[dict]:
    papers_dir = root / "data" / "papers"
    manifest_path = papers_dir / "manifest.json"
    pdf_files = sorted(path.name for path in papers_dir.glob("*.pdf")) if papers_dir.exists() else []
    checks = [
        _result(
            "paper_count",
            "data/papers",
            "pass" if 5 <= len(pdf_files) <= 10 else "fail",
            f"Found {len(pdf_files)} local PDFs; MVP target is 5-10.",
        )
    ]
    if not manifest_path.exists():
        checks.append(_result("paper_manifest", "data/papers/manifest.json", "fail", "Manifest is missing."))
        return checks
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_files = sorted(item.get("filename", "") for item in manifest.get("papers", []))
    missing_from_manifest = sorted(set(pdf_files) - set(manifest_files))
    missing_from_disk = sorted(set(manifest_files) - set(pdf_files))
    status = "pass" if not missing_from_manifest and not missing_from_disk else "fail"
    checks.append(
        _result(
            "paper_manifest",
            "data/papers/manifest.json",
            status,
            "Manifest matches local PDFs."
            if status == "pass"
            else f"Manifest mismatch. Missing from manifest: {missing_from_manifest}; missing from disk: {missing_from_disk}",
        )
    )
    return checks


def _check_evaluation_report(root: Path, min_overall_score: float) -> list[dict]:
    path = root / "data" / "processed" / "evaluation_report.json"
    if not path.exists():
        return [_result("evaluation_report", str(path), "fail", "Evaluation report is missing.")]
    report = json.loads(path.read_text(encoding="utf-8"))
    failed_checks = report.get("failed_checks", [])
    overall_score = float(report.get("overall_score", 0.0))
    warnings = report.get("warnings", [])
    return [
        _result(
            "evaluation_failed_checks",
            "data/processed/evaluation_report.json",
            "pass" if not failed_checks else "fail",
            f"Failed checks: {len(failed_checks)}",
        ),
        _result(
            "evaluation_overall_score",
            "data/processed/evaluation_report.json",
            "pass" if overall_score >= min_overall_score else "fail",
            f"Overall score {overall_score}; threshold {min_overall_score}.",
        ),
        _result(
            "evaluation_warnings",
            "data/processed/evaluation_report.json",
            "warn" if warnings else "pass",
            f"Warnings present: {len(warnings)}. Review before presenting." if warnings else "No evaluation warnings.",
        ),
    ]


def _check_golden_report(root: Path, min_pass_rate: float) -> list[dict]:
    path = root / "data" / "processed" / "golden_eval_report.json"
    if not path.exists():
        return [_result("golden_eval_report", str(path), "fail", "Golden eval report is missing.")]
    report = json.loads(path.read_text(encoding="utf-8"))
    pass_rate = float(report.get("pass_rate", 0.0))
    failed_cases = int(report.get("failed_cases", 0))
    return [
        _result(
            "golden_eval_pass_rate",
            "data/processed/golden_eval_report.json",
            "pass" if pass_rate >= min_pass_rate else "fail",
            f"Golden pass rate {pass_rate}; threshold {min_pass_rate}.",
        ),
        _result(
            "golden_eval_failed_cases",
            "data/processed/golden_eval_report.json",
            "pass" if failed_cases == 0 else "fail",
            f"Failed golden cases: {failed_cases}.",
        ),
    ]


def _check_project_stats(root: Path) -> list[dict]:
    db_path = root / "data" / "processed" / "papers.sqlite"
    if not db_path.exists():
        return [_result("project_stats", str(db_path), "fail", "SQLite database is missing.")]
    stats = calculate_project_stats(str(db_path))
    return [
        _result("stats_papers", "project_stats", "pass" if 5 <= stats["papers"] <= 10 else "fail", f"Papers: {stats['papers']}."),
        _result("stats_statements", "project_stats", "pass" if stats["statements"] > 0 else "fail", f"Statements: {stats['statements']}."),
        _result("stats_graph_size", "project_stats", "pass" if stats["graph_nodes"] <= 3000 else "warn", f"Graph nodes: {stats['graph_nodes']}."),
    ]


def _check_docs_content(root: Path) -> list[dict]:
    readme = (root / "README.md").read_text(encoding="utf-8") if (root / "README.md").exists() else ""
    required_phrases = [
        "Competition Demo",
        "Architecture",
        "ADK Prototype Entry Point",
        "capstone_evaluation_mapping.md",
        "Known Limitations",
    ]
    checks = []
    for phrase in required_phrases:
        checks.append(
            _result(
                "readme_section",
                phrase,
                "pass" if phrase in readme else "warn",
                "README section present." if phrase in readme else "README could better explain this section.",
            )
        )
    return checks


def _result(category: str, name: str, status: str, message: str) -> dict:
    return {
        "category": category,
        "name": name,
        "status": status,
        "message": message,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate local competition submission readiness.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--min-overall-score", type=float, default=0.75)
    parser.add_argument("--min-golden-pass-rate", type=float, default=1.0)
    parser.add_argument("--output-path", default="data/processed/submission_validation_report.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = validate_submission(
            args.project_root,
            min_overall_score=args.min_overall_score,
            min_golden_pass_rate=args.min_golden_pass_rate,
        )
        output_path = _resolve_local_path(args.output_path, "output_path")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        log_error("submission_validation.failed", str(exc))
        return 1

    summary = report["summary"]
    log_info(
        "submission_validation.completed",
        ready=report["ready"],
        passed=summary["passed"],
        warnings=summary["warnings"],
        failed=summary["failed"],
        report=args.output_path,
    )
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
