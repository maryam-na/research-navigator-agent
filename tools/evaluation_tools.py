"""Deterministic evaluation metrics for generated research outputs."""

from __future__ import annotations

import re

from tools.safety_tools import (
    check_hypothesis_safety,
    check_overclaiming,
    detect_prompt_injection,
    validate_evidence_grounding,
)


GENERIC_PLAN_PHRASES = (
    "task-specific performance metric",
    "current method or reported setup",
    "where available",
    "local, open-access or synthetic data",
)


def evaluate_outputs(
    gaps: list[dict],
    hypotheses: list[dict],
    experiment_plans: list[dict],
    statements: list[dict],
) -> dict:
    failed_checks: list[dict] = []
    warnings: list[dict] = []
    grounding_score = compute_grounding_score(gaps, hypotheses, statements, failed_checks)
    safety_score = compute_safety_score(gaps, hypotheses, experiment_plans, failed_checks)
    testability_score = compute_testability_score(hypotheses, experiment_plans, failed_checks)
    traceability_score = compute_traceability_score(
        gaps,
        hypotheses,
        experiment_plans,
        failed_checks,
    )
    metric_details = compute_metric_details(gaps, hypotheses, experiment_plans, statements)
    warnings.extend(metric_details["warnings"])
    overall_score = round(
        (
            grounding_score * 0.3
            + safety_score * 0.25
            + testability_score * 0.25
            + traceability_score * 0.2
        ),
        3,
    )
    return {
        "total_gaps": len(gaps),
        "total_hypotheses": len(hypotheses),
        "total_experiment_plans": len(experiment_plans),
        "total_evaluated_items": len(gaps) + len(hypotheses) + len(experiment_plans),
        "overall_score": overall_score,
        "grounding_score": grounding_score,
        "safety_score": safety_score,
        "testability_score": testability_score,
        "traceability_score": traceability_score,
        "metric_details": metric_details,
        "warnings": warnings,
        "failed_checks": failed_checks,
    }


def compute_grounding_score(
    gaps: list[dict],
    hypotheses: list[dict],
    statements: list[dict],
    failed_checks: list[dict] | None = None,
) -> float:
    items = [*gaps, *hypotheses]
    if not items:
        return 0.0
    statement_lookup = {str(statement.get("statement_id", "")): statement for statement in statements}
    item_scores = []
    for item in items:
        result = validate_evidence_grounding(item, statements)
        if result["passed"]:
            evidence_ids = result["evidence_statement_ids"]
            evidence_count_score = min(len(evidence_ids), 3) / 3
            paper_count = len(
                {
                    str(statement_lookup[statement_id].get("paper_id", ""))
                    for statement_id in evidence_ids
                    if statement_id in statement_lookup
                }
            )
            paper_diversity_score = min(paper_count, 2) / 2 if paper_count else 0
            evidence_text_score = _evidence_text_score(item, statement_lookup)
            item_scores.append(
                (0.55)
                + (0.2 * evidence_count_score)
                + (0.15 * paper_diversity_score)
                + (0.1 * evidence_text_score)
            )
        elif failed_checks is not None:
            failed_checks.append(
                {
                    "check": "grounding",
                    "item_id": _item_id(item),
                    "missing_evidence_statement_ids": result["missing_evidence_statement_ids"],
                }
            )
            item_scores.append(0.0)
    return round(sum(item_scores) / len(items), 3)


def compute_safety_score(
    gaps: list[dict],
    hypotheses: list[dict],
    experiment_plans: list[dict],
    failed_checks: list[dict] | None = None,
) -> float:
    checked_items = []
    for gap in gaps:
        checked_items.append(("gap", _item_id(gap), str(gap.get("gap_text", ""))))
    for hypothesis in hypotheses:
        checked_items.append(("hypothesis", _item_id(hypothesis), str(hypothesis.get("hypothesis_text", ""))))
        hypothesis_safety = check_hypothesis_safety(hypothesis)
        if not hypothesis_safety["passed"] and failed_checks is not None:
            failed_checks.append(
                {
                    "check": "hypothesis_safety",
                    "item_id": _item_id(hypothesis),
                    "failed_checks": hypothesis_safety["failed_checks"],
                }
            )
    for plan in experiment_plans:
        checked_items.append(("experiment_plan", _item_id(plan), _plan_text(plan)))

    if not checked_items:
        return 0.0

    item_scores = []
    for item_type, item_id, text in checked_items:
        prompt_result = detect_prompt_injection(text)
        overclaim_result = check_overclaiming(text)
        item_passed = prompt_result["passed"] and overclaim_result["passed"]
        if item_passed:
            caution_score = 1.0 if _has_cautious_language(text) else 0.75
            item_scores.append(0.85 + (0.15 * caution_score))
        elif failed_checks is not None:
            failed_checks.append(
                {
                    "check": "safety_text",
                    "item_type": item_type,
                    "item_id": item_id,
                    "prompt_injection_patterns": prompt_result["matched_patterns"],
                    "overclaiming_patterns": overclaim_result["matched_patterns"],
                }
            )
            item_scores.append(0.0)
    hypothesis_results = [check_hypothesis_safety(hypothesis) for hypothesis in hypotheses]
    if hypothesis_results:
        hypothesis_safety_score = sum(1 for result in hypothesis_results if result["passed"]) / len(hypothesis_results)
        item_scores.append(hypothesis_safety_score)
    return round(sum(item_scores) / len(item_scores), 3)


def compute_testability_score(
    hypotheses: list[dict],
    experiment_plans: list[dict],
    failed_checks: list[dict] | None = None,
) -> float:
    if not hypotheses:
        return 0.0

    plan_by_hypothesis = {
        str(plan.get("hypothesis_id", "")): plan.get("plan", plan)
        for plan in experiment_plans
    }
    item_scores = []
    for hypothesis in hypotheses:
        hypothesis_id = str(hypothesis.get("hypothesis_id", ""))
        text = str(hypothesis.get("hypothesis_text", "")).lower()
        plan = plan_by_hypothesis.get(hypothesis_id, {})
        has_testable_language = "testable" in text or "test " in text
        has_required_plan_fields = all(
            bool(plan.get(field))
            for field in (
                "objective",
                "required_data",
                "method",
                "baseline_or_control",
                "metrics",
                "expected_outcome",
                "risks_and_limitations",
            )
        )
        specificity_score = _plan_specificity_score(plan)
        metrics_score = min(len(plan.get("metrics", [])), 3) / 3 if isinstance(plan.get("metrics"), list) else 0.0
        item_score = (
            (0.35 if has_testable_language else 0.0)
            + (0.35 if has_required_plan_fields else 0.0)
            + (0.15 * metrics_score)
            + (0.15 * specificity_score)
        )
        if has_testable_language and has_required_plan_fields:
            item_scores.append(item_score)
        elif failed_checks is not None:
            failed_checks.append(
                {
                    "check": "testability",
                    "item_id": hypothesis_id,
                    "has_testable_language": has_testable_language,
                    "has_required_plan_fields": has_required_plan_fields,
                }
            )
            item_scores.append(item_score)
    return round(sum(item_scores) / len(hypotheses), 3)


def compute_traceability_score(
    gaps: list[dict],
    hypotheses: list[dict],
    experiment_plans: list[dict],
    failed_checks: list[dict] | None = None,
) -> float:
    items = [*gaps, *hypotheses, *experiment_plans]
    if not items:
        return 0.0

    gap_ids = {str(gap.get("gap_id", "")) for gap in gaps}
    hypothesis_ids = {str(hypothesis.get("hypothesis_id", "")) for hypothesis in hypotheses}
    passed = 0
    for item in items:
        item_id = _item_id(item)
        item_passed = True
        if "gap_id" in item and item.get("gap_id") not in gap_ids:
            item_passed = False
        if "hypothesis_id" in item and "plan" in item and item.get("hypothesis_id") not in hypothesis_ids:
            item_passed = False
        if "source_statement_ids" in item and not item.get("source_statement_ids"):
            item_passed = False
        if "evidence_statement_ids" in item and not item.get("evidence_statement_ids"):
            item_passed = False
        if item_passed:
            passed += 1
        elif failed_checks is not None:
            failed_checks.append({"check": "traceability", "item_id": item_id})
    return round(passed / len(items), 3)


def compute_metric_details(
    gaps: list[dict],
    hypotheses: list[dict],
    experiment_plans: list[dict],
    statements: list[dict],
) -> dict:
    """Return interpretable evaluation details beyond headline scores."""

    warnings = []
    total_outputs = len(gaps) + len(hypotheses) + len(experiment_plans)
    evidence_ids = []
    for gap in gaps:
        evidence_ids.extend(str(item) for item in gap.get("source_statement_ids", []))
    for hypothesis in hypotheses:
        evidence_ids.extend(str(item) for item in hypothesis.get("evidence_statement_ids", []))
    unique_evidence_ids = sorted(set(evidence_ids))
    statement_ids = {str(statement.get("statement_id", "")) for statement in statements}
    paper_ids = {
        str(statement.get("paper_id", ""))
        for statement in statements
        if statement.get("paper_id")
    }
    evidence_papers = {
        str(statement.get("paper_id", ""))
        for statement in statements
        if str(statement.get("statement_id", "")) in unique_evidence_ids and statement.get("paper_id")
    }
    missing_evidence_ids = [statement_id for statement_id in unique_evidence_ids if statement_id not in statement_ids]
    average_evidence_per_gap = round(
        sum(len(gap.get("source_statement_ids", [])) for gap in gaps) / len(gaps),
        3,
    ) if gaps else 0.0
    average_evidence_per_hypothesis = round(
        sum(len(hypothesis.get("evidence_statement_ids", [])) for hypothesis in hypotheses) / len(hypotheses),
        3,
    ) if hypotheses else 0.0
    plan_specificity_score = round(
        sum(_plan_specificity_score(plan.get("plan", plan)) for plan in experiment_plans) / len(experiment_plans),
        3,
    ) if experiment_plans else 0.0

    if total_outputs == 0:
        warnings.append({"level": "warning", "message": "No generated outputs were available to evaluate."})
    if len(unique_evidence_ids) < max(3, min(total_outputs, 10)):
        warnings.append({"level": "warning", "message": "Outputs rely on a small set of evidence statements."})
    if len(evidence_papers) <= 1 and total_outputs:
        warnings.append({"level": "info", "message": "Evidence currently comes from one paper or fewer."})
    if plan_specificity_score < 0.75 and experiment_plans:
        warnings.append({"level": "info", "message": "Experiment plans are structurally complete but still generic."})

    return {
        "evaluated_output_count": total_outputs,
        "statement_count": len(statements),
        "paper_count": len(paper_ids),
        "unique_evidence_statement_count": len(unique_evidence_ids),
        "missing_evidence_statement_count": len(missing_evidence_ids),
        "evidence_paper_count": len(evidence_papers),
        "average_evidence_per_gap": average_evidence_per_gap,
        "average_evidence_per_hypothesis": average_evidence_per_hypothesis,
        "plan_specificity_score": plan_specificity_score,
        "warnings": warnings,
    }


def _item_id(item: dict) -> str:
    return str(
        item.get("gap_id")
        or item.get("hypothesis_id")
        or item.get("statement_id")
        or "unknown"
    )


def _plan_text(plan_item: dict) -> str:
    plan = plan_item.get("plan", plan_item)
    values = []
    for value in plan.values():
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        else:
            values.append(str(value))
    return " ".join(values)


def _evidence_text_score(item: dict, statement_lookup: dict[str, dict]) -> float:
    evidence_ids = item.get("evidence_statement_ids") or item.get("source_statement_ids") or []
    snippets = []
    for statement_id in evidence_ids:
        statement = statement_lookup.get(str(statement_id), {})
        snippets.append(str(statement.get("evidence_text", "") or statement.get("statement_text", "")))
    snippets.extend(str(snippet) for snippet in item.get("evidence_text", []) if snippet)
    if not snippets:
        return 0.0
    average_length = sum(len(snippet.strip()) for snippet in snippets) / len(snippets)
    return min(1.0, average_length / 160)


def _has_cautious_language(text: str) -> bool:
    normalized = text.lower()
    return any(
        phrase in normalized
        for phrase in (
            "could",
            "candidate",
            "may",
            "might",
            "possible",
            "speculative",
            "would be supported",
        )
    )


def _plan_specificity_score(plan: dict) -> float:
    if not plan:
        return 0.0
    text = _plan_text(plan).lower()
    if not text.strip():
        return 0.0
    generic_hits = sum(1 for phrase in GENERIC_PLAN_PHRASES if phrase in text)
    field_values = [value for value in plan.values() if value]
    length_score = min(1.0, len(re.findall(r"[a-z0-9]+", text)) / 80)
    field_score = min(1.0, len(field_values) / 7)
    generic_penalty = min(0.45, generic_hits * 0.12)
    return round(max(0.0, (length_score * 0.45) + (field_score * 0.55) - generic_penalty), 3)
