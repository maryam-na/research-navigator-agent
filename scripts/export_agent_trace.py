"""Export a deterministic demo trace for the local ResearchNavigator agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.storage_tools import get_statements


DEFAULT_DB_PATH = Path("data/processed/papers.sqlite")
DEFAULT_DISCOVERY_PATH = Path("data/processed/gaps_and_hypotheses.json")
DEFAULT_OUTPUT_PATH = Path("data/generated/agent_trace_demo.json")
DEFAULT_QUESTION = "Which research gaps in the local corpus are supported by evidence IDs?"
FALLBACK_EVIDENCE_IDS = ["stmt_demo_evidence_001", "stmt_demo_evidence_002"]


def build_agent_trace(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    discovery_path: str | Path = DEFAULT_DISCOVERY_PATH,
    user_question: str = DEFAULT_QUESTION,
) -> dict[str, Any]:
    """Build a deterministic trace from local artifacts, with a stable fallback."""

    db = Path(db_path)
    discovery_file = Path(discovery_path)
    statements = _load_statements(db)
    discovery = _load_json(discovery_file)
    evidence_ids = _select_evidence_ids(discovery, statements)
    evidence_preview = _evidence_preview(evidence_ids, statements)
    top_gap = _first_item(discovery.get("gaps", []))
    top_hypothesis = _first_item(discovery.get("hypotheses", []))
    final_text = _final_answer(user_question, evidence_ids, top_gap, top_hypothesis)

    steps = [
        {
            "order": 1,
            "step_type": "planning",
            "tool_name": "planned_tool_trajectory",
            "purpose": "Plan the local research-discovery tool path before answering.",
            "input_summary": f"User question: {user_question}",
            "output_summary": "Plan: ingest, extract, retrieve evidence, build graph, discover gaps, evaluate, then answer with evidence IDs.",
            "safety_gate": "policy_gates_visible",
        },
        {
            "order": 2,
            "step_type": "ingestion",
            "tool_name": "ingest_local_papers",
            "purpose": "Load permitted local PDFs and convert them into SQLite records.",
            "input_summary": "Local PDF corpus in data/papers; no external browsing or API keys.",
            "output_summary": f"Structured local statements available: {len(statements)}.",
            "safety_gate": "prompt_injection_treated_as_data",
        },
        {
            "order": 3,
            "step_type": "retrieval",
            "tool_name": "search_local_corpus",
            "purpose": "Retrieve local statements relevant to the research question.",
            "input_summary": "Search processed papers, statements, gaps, hypotheses, and plans.",
            "output_summary": f"Selected evidence IDs: {', '.join(evidence_ids)}.",
            "safety_gate": "local_processed_artifacts_only",
        },
        {
            "order": 4,
            "step_type": "grounding",
            "tool_name": "inspect_evidence",
            "purpose": "Inspect source statement metadata before using evidence in an answer.",
            "input_summary": f"Evidence IDs requested: {', '.join(evidence_ids)}.",
            "output_summary": f"Evidence rows inspected: {len(evidence_preview)}.",
            "safety_gate": "evidence_id_traceability",
        },
        {
            "order": 5,
            "step_type": "graph_discovery",
            "tool_name": "build_local_graph",
            "purpose": "Represent local papers and extracted statements as a NetworkX graph.",
            "input_summary": "SQLite statements and local graph artifact path.",
            "output_summary": "Graph supports relationship review before gap discovery.",
            "safety_gate": "graph_size_checked",
        },
        {
            "order": 6,
            "step_type": "gap_and_hypothesis_generation",
            "tool_name": "discover_local_research_gaps",
            "purpose": "Generate evidence-backed gaps and speculative hypotheses from local statements.",
            "input_summary": "Grounded statements and graph relationships from the local corpus.",
            "output_summary": _discovery_summary(top_gap, top_hypothesis),
            "safety_gate": "evidence_required",
        },
        {
            "order": 7,
            "step_type": "safety_check",
            "tool_name": "evaluate_local_outputs",
            "purpose": "Check grounding, overclaiming, testability, and traceability before answering.",
            "input_summary": "Generated gaps, hypotheses, experiment plans, and local statements.",
            "output_summary": "Final answer is allowed only with evidence IDs and speculative labels.",
            "safety_gate": "overclaiming_and_unsupported_claim_checks",
        },
        {
            "order": 8,
            "step_type": "final_answer",
            "tool_name": "compose_grounded_answer",
            "purpose": "Produce a concise answer grounded in local evidence IDs.",
            "input_summary": "Question, inspected evidence rows, evaluated gap, and speculative hypothesis.",
            "output_summary": final_text,
            "safety_gate": "human_review_required_for_research_use",
        },
    ]

    return {
        "trace_id": "researchnavigator_deterministic_capstone_trace_v1",
        "mode": "local_offline_deterministic_baseline",
        "agent_framing": "ADK-facing tool-orchestrating research discovery agent",
        "user_research_question": user_question,
        "steps": steps,
        "evidence_preview": evidence_preview,
        "final_answer": {
            "text": final_text,
            "evidence_ids": evidence_ids,
            "safety_labels": ["grounded", "speculative_research_hypothesis", "human_review_required"],
        },
        "limits": [
            "Uses only local processed artifacts.",
            "Does not train or fine-tune models.",
            "Does not call external APIs.",
            "Generated hypotheses are speculative and require human review.",
        ],
    }


def export_agent_trace(
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    discovery_path: str | Path = DEFAULT_DISCOVERY_PATH,
    user_question: str = DEFAULT_QUESTION,
) -> dict[str, Any]:
    """Write the deterministic trace and return it."""

    trace = build_agent_trace(
        db_path=db_path,
        discovery_path=discovery_path,
        user_question=user_question,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return trace


def validate_agent_trace(trace: dict[str, Any]) -> list[str]:
    """Return validation errors for a trace payload."""

    errors: list[str] = []
    steps = list(trace.get("steps", []) or [])
    if len(steps) < 5:
        errors.append("trace must include at least 5 steps")
    required_step_fields = {"tool_name", "purpose", "input_summary", "output_summary"}
    for index, step in enumerate(steps, start=1):
        missing = sorted(required_step_fields - set(step))
        if missing:
            errors.append(f"step {index} missing fields: {', '.join(missing)}")
    safety_positions = [
        index for index, step in enumerate(steps) if step.get("step_type") == "safety_check"
    ]
    final_positions = [
        index for index, step in enumerate(steps) if step.get("step_type") == "final_answer"
    ]
    if not safety_positions:
        errors.append("trace must include a safety_check step")
    if not final_positions:
        errors.append("trace must include a final_answer step")
    if safety_positions and final_positions and min(safety_positions) > min(final_positions):
        errors.append("safety_check must appear before final_answer")
    final_answer = dict(trace.get("final_answer", {}) or {})
    answer_text = str(final_answer.get("text", ""))
    evidence_ids = [str(item) for item in final_answer.get("evidence_ids", []) if str(item)]
    if not evidence_ids:
        errors.append("final answer must include evidence IDs")
    missing_ids = [evidence_id for evidence_id in evidence_ids if evidence_id not in answer_text]
    if missing_ids:
        errors.append(f"final answer text must reference evidence IDs: {', '.join(missing_ids)}")
    return errors


def _load_statements(db_path: Path) -> list[dict]:
    if not db_path.exists():
        return []
    try:
        return get_statements(str(db_path))
    except Exception:
        return []


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _select_evidence_ids(discovery: dict[str, Any], statements: list[dict]) -> list[str]:
    selected: list[str] = []
    for collection_name in ("gaps", "hypotheses"):
        for item in discovery.get(collection_name, []) or []:
            for statement_id in item.get("evidence_statement_ids", []) or []:
                _append_unique(selected, str(statement_id))
            if len(selected) >= 2:
                return selected[:3]
    for statement in statements[:3]:
        _append_unique(selected, str(statement.get("statement_id", "")))
    return selected or FALLBACK_EVIDENCE_IDS.copy()


def _append_unique(values: list[str], value: str) -> None:
    clean_value = value.strip()
    if clean_value and clean_value not in values:
        values.append(clean_value)


def _evidence_preview(evidence_ids: list[str], statements: list[dict]) -> list[dict[str, str]]:
    by_id = {str(statement.get("statement_id", "")): statement for statement in statements}
    rows = []
    for statement_id in evidence_ids:
        statement = by_id.get(statement_id, {})
        rows.append(
            {
                "statement_id": statement_id,
                "paper_id": str(statement.get("paper_id", "local-demo")),
                "statement_type": str(statement.get("statement_type", "evidence")),
                "snippet": _clip(str(statement.get("evidence_text") or statement.get("statement_text") or "")),
            }
        )
    return rows


def _first_item(items: Any) -> dict[str, Any]:
    if isinstance(items, list) and items and isinstance(items[0], dict):
        return items[0]
    return {}


def _discovery_summary(gap: dict[str, Any], hypothesis: dict[str, Any]) -> str:
    gap_id = str(gap.get("gap_id", "gap_demo_local"))
    hypothesis_id = str(hypothesis.get("hypothesis_id", "hyp_demo_local"))
    safety_label = str(hypothesis.get("safety_label", "speculative_research_hypothesis"))
    return f"Generated gap {gap_id} and hypothesis {hypothesis_id} with safety label {safety_label}."


def _final_answer(
    question: str,
    evidence_ids: list[str],
    gap: dict[str, Any],
    hypothesis: dict[str, Any],
) -> str:
    gap_id = str(gap.get("gap_id", "gap_demo_local"))
    hypothesis_id = str(hypothesis.get("hypothesis_id", "hyp_demo_local"))
    evidence_text = ", ".join(evidence_ids)
    return (
        f"For the question '{question}', the local corpus supports a bounded research gap "
        f"({gap_id}) using evidence IDs {evidence_text}. A candidate hypothesis "
        f"({hypothesis_id}) is speculative, not proven, and should be reviewed by a human "
        f"before use beyond the demo."
    )


def _clip(text: str, max_chars: int = 180) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export the deterministic demo agent trace.")
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--discovery-path", default=str(DEFAULT_DISCOVERY_PATH))
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--json", action="store_true", help="Print the trace payload.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    trace = export_agent_trace(
        args.output_path,
        db_path=args.db_path,
        discovery_path=args.discovery_path,
        user_question=args.question,
    )
    errors = validate_agent_trace(trace)
    if args.json:
        print(json.dumps(trace, indent=2, sort_keys=True))
    else:
        print(f"Exported deterministic agent trace to {args.output_path}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
