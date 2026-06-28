"""Deterministic local safety and grounding checks."""

from __future__ import annotations

import re

from tools.extraction_tools import normalize_statement_text


PROMPT_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "system prompt",
    "developer message",
    "jailbreak",
    "disregard all rules",
)

OVERCLAIMING_PATTERNS = (
    "proves",
    "guarantees",
    "definitively shows",
    "cures",
    "fully solves",
    "proof that no one has solved",
    "no one has solved",
)


def detect_prompt_injection(text: str) -> dict:
    normalized = normalize_statement_text(text).lower()
    matches = [pattern for pattern in PROMPT_INJECTION_PATTERNS if pattern in normalized]
    return {
        "passed": not matches,
        "prompt_injection_detected": bool(matches),
        "matched_patterns": matches,
    }


def check_overclaiming(text: str) -> dict:
    normalized = normalize_statement_text(text).lower()
    matches = [
        pattern
        for pattern in OVERCLAIMING_PATTERNS
        if re.search(rf"\b{re.escape(pattern)}\b", normalized)
    ]
    return {
        "passed": not matches,
        "overclaiming_detected": bool(matches),
        "matched_patterns": matches,
    }


def validate_evidence_grounding(item: dict, statements: list[dict]) -> dict:
    evidence_ids = _evidence_ids_for_item(item)
    existing_ids = {str(statement.get("statement_id", "")) for statement in statements}
    missing_ids = [statement_id for statement_id in evidence_ids if statement_id not in existing_ids]
    return {
        "passed": bool(evidence_ids) and not missing_ids,
        "evidence_statement_ids": evidence_ids,
        "missing_evidence_statement_ids": missing_ids,
    }


def check_hypothesis_safety(hypothesis: dict) -> dict:
    text = str(hypothesis.get("hypothesis_text", ""))
    prompt_injection = detect_prompt_injection(text)
    overclaiming = check_overclaiming(text)
    has_speculative_label = hypothesis.get("safety_label") == "speculative_research_hypothesis"
    evidence_ids = [
        str(statement_id)
        for statement_id in hypothesis.get("evidence_statement_ids", [])
        if str(statement_id).strip()
    ]
    passed = (
        prompt_injection["passed"]
        and overclaiming["passed"]
        and has_speculative_label
        and bool(evidence_ids)
    )
    failed_checks = []
    if not prompt_injection["passed"]:
        failed_checks.append("prompt_injection")
    if not overclaiming["passed"]:
        failed_checks.append("overclaiming")
    if not has_speculative_label:
        failed_checks.append("missing_speculative_label")
    if not evidence_ids:
        failed_checks.append("missing_evidence_statement_ids")

    return {
        "passed": passed,
        "failed_checks": failed_checks,
        "has_speculative_label": has_speculative_label,
        "evidence_statement_ids": evidence_ids,
        "prompt_injection": prompt_injection,
        "overclaiming": overclaiming,
    }


def _evidence_ids_for_item(item: dict) -> list[str]:
    ids = item.get("evidence_statement_ids")
    if ids is None:
        ids = item.get("source_statement_ids")
    return [str(statement_id) for statement_id in ids or [] if str(statement_id).strip()]
