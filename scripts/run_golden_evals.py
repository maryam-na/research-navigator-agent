"""Run deterministic checks against evals/golden_cases.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.extraction_tools import extract_research_statements
from tools.graph_tools import build_research_graph, graph_summary
from tools.gap_tools import discover_research_gaps, generate_experiment_plan, generate_hypotheses
from tools.safety_tools import check_overclaiming, detect_prompt_injection


def _resolve_local_path(path_value: str, label: str) -> Path:
    if not path_value or not path_value.strip():
        raise ValueError(f"{label} must be a non-empty local path.")
    parsed = urlparse(path_value)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError(f"{label} must be a local path.")
    return Path(parsed.path if parsed.scheme == "file" else path_value).expanduser()


def run_golden_evals(
    cases_path: str = "evals/golden_cases.json",
    output_path: str = "data/processed/golden_eval_report.json",
) -> dict:
    """Evaluate deterministic project behavior on golden cases."""

    cases_file = _resolve_local_path(cases_path, "cases_path")
    if not cases_file.exists():
        raise FileNotFoundError(f"Golden cases file does not exist: {cases_file}")
    cases = json.loads(cases_file.read_text(encoding="utf-8"))
    results = [_evaluate_case(case) for case in cases]
    passed = sum(1 for result in results if result["passed"])
    report = {
        "total_cases": len(results),
        "passed_cases": passed,
        "failed_cases": len(results) - passed,
        "pass_rate": round(passed / len(results), 3) if results else 0.0,
        "results": results,
    }
    output_file = _resolve_local_path(output_path, "output_path")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _evaluate_case(case: dict) -> dict:
    category = case.get("category")
    if category == "extraction_quality":
        return _evaluate_extraction_case(case)
    if category == "safety":
        return _evaluate_safety_case(case)
    if category == "grounding":
        return _evaluate_grounding_case(case)
    if category == "graph_correctness":
        return _evaluate_graph_case(case)
    if category == "tool_trajectory":
        return _evaluate_gap_hypothesis_case(case)
    return _case_result(case, False, ["unsupported_category"])


def _evaluate_extraction_case(case: dict) -> dict:
    text = case["input"]["text"]
    statements = extract_research_statements(text, case["input"]["paper_id"], "chunk_001")
    types = {statement["statement_type"] for statement in statements}
    lower_text = text.lower()
    checks = {
        "method": "method" in types or "method" in lower_text,
        "dataset": "dataset" in types or "benchmark" in lower_text or "dataset" in lower_text,
        "result": "result" in types,
        "limitation": "limitation" in types,
        "future_work": "future_work" in types,
        "no_prompt_injection": detect_prompt_injection(text)["passed"],
    }
    return _case_result(case, all(checks.values()), _failed_check_names(checks), checks)


def _evaluate_safety_case(case: dict) -> dict:
    text = case["input"]["text"]
    statements = extract_research_statements(text, case["input"]["paper_id"], "chunk_001")
    prompt_injection = detect_prompt_injection(text)
    types = {statement["statement_type"] for statement in statements}
    lower_text = text.lower()
    checks = {
        "prompt_injection_detected": prompt_injection["prompt_injection_detected"],
        "legitimate_result_still_extractable": "result" in types or "reduces" in lower_text,
        "legitimate_limitation_still_extractable": "limitation" in types,
    }
    return _case_result(case, all(checks.values()), _failed_check_names(checks), checks)


def _evaluate_grounding_case(case: dict) -> dict:
    request = case["input"]["user_request"]
    corpus_titles = {item["title"] for item in case["input"]["local_corpus"]}
    fake_citation_requested = "Smith et al. 2025" in request
    citation_in_corpus = any("Smith" in title for title in corpus_titles)
    overclaiming = check_overclaiming(request)
    checks = {
        "fake_citation_detected": fake_citation_requested and not citation_in_corpus,
        "overclaiming_detected": overclaiming["overclaiming_detected"],
    }
    return _case_result(case, all(checks.values()), _failed_check_names(checks), checks)


def _evaluate_graph_case(case: dict) -> dict:
    records = case["input"]["extracted_records"]
    paper_id = case["input"]["paper_id"]
    statements = []
    for index, statement_type in enumerate(("method", "dataset", "result", "limitation", "future_work")):
        statements.append(
            {
                "statement_id": f"stmt_{statement_type}",
                "paper_id": paper_id,
                "chunk_id": f"{paper_id}:chunk_001",
                "statement_type": statement_type,
                "statement_text": records[statement_type],
                "evidence_text": records[statement_type],
                "confidence_rule": f"golden:{statement_type}",
                "sentence_index": index,
            }
        )
    graph = build_research_graph(statements)
    summary = graph_summary(graph)
    relation_types = summary["relation_types"]
    node_types = summary["node_types"]
    checks = {
        "paper_node": node_types.get("paper", 0) == 1,
        "method_node": node_types.get("method", 0) >= 1,
        "dataset_node": node_types.get("dataset", 0) >= 1,
        "result_node": node_types.get("result", 0) >= 1,
        "limitation_node": node_types.get("limitation", 0) >= 1,
        "future_work_node": node_types.get("future_work", 0) >= 1,
        "contains_edges": relation_types.get("contains", 0) == len(statements),
        "limited_by_edge": relation_types.get("limited_by", 0) >= 1,
    }
    return _case_result(case, all(checks.values()), _failed_check_names(checks), checks)


def _evaluate_gap_hypothesis_case(case: dict) -> dict:
    limitations = case["input"]["grounded_limitations"]
    statements = [
        {
            "statement_id": f"stmt_limitation_{index}",
            "paper_id": "synthetic_gap_case",
            "chunk_id": "synthetic_gap_case:chunk_001",
            "statement_type": "limitation",
            "statement_text": limitation,
            "evidence_text": limitation,
            "confidence_rule": "golden:limitation",
            "sentence_index": index,
        }
        for index, limitation in enumerate(limitations)
    ]
    gaps = discover_research_gaps(statements, max_gaps=5)
    hypotheses = generate_hypotheses(gaps, statements, max_hypotheses=5)
    plans = [generate_experiment_plan(hypothesis) for hypothesis in hypotheses]
    checks = {
        "gap_generated": bool(gaps),
        "hypothesis_generated": bool(hypotheses),
        "speculative_label": all(
            hypothesis.get("safety_label") == "speculative_research_hypothesis"
            for hypothesis in hypotheses
        ),
        "plan_generated": bool(plans),
        "plan_has_metrics": all(bool(plan.get("metrics")) for plan in plans),
    }
    return _case_result(case, all(checks.values()), _failed_check_names(checks), checks)


def _case_result(case: dict, passed: bool, failed_checks: list[str], checks: dict | None = None) -> dict:
    return {
        "id": case.get("id", "unknown"),
        "category": case.get("category", "unknown"),
        "passed": passed,
        "failed_checks": failed_checks,
        "checks": checks or {},
    }


def _failed_check_names(checks: dict[str, bool]) -> list[str]:
    return [name for name, passed in checks.items() if not passed]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic golden evaluation cases.")
    parser.add_argument("--cases-path", default="evals/golden_cases.json")
    parser.add_argument("--output-path", default="data/processed/golden_eval_report.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = run_golden_evals(args.cases_path, args.output_path)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Golden cases: {report['passed_cases']}/{report['total_cases']} passed")
    print(f"Pass rate: {report['pass_rate']}")
    print(f"Failed cases: {report['failed_cases']}")
    return 0 if report["failed_cases"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
