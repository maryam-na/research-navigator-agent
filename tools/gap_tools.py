"""Deterministic research gap, hypothesis, and experiment-plan generation."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from tools.extraction_tools import normalize_statement_text

MAX_GAP_EVIDENCE_CHARS = 240


def discover_research_gaps(statements: list[dict], max_gaps: int = 10) -> list[dict]:
    """Discover evidence-backed candidate research gaps from extracted statements."""

    if max_gaps <= 0:
        raise ValueError("max_gaps must be greater than 0.")

    sorted_statements = sorted(statements, key=_statement_sort_key)
    limitations = [item for item in sorted_statements if item.get("statement_type") == "limitation"]
    future_work = [item for item in sorted_statements if item.get("statement_type") == "future_work"]
    results = [item for item in sorted_statements if item.get("statement_type") == "result"]

    gaps: list[dict] = []
    seen_gap_keys: set[tuple[str, tuple[str, ...]]] = set()

    for statement in limitations:
        gap = _gap_from_statements(
            "limitation",
            "A possible research gap is suggested by a reported limitation: "
            f"{_clean_gap_phrase(statement)}",
            [statement],
        )
        _append_gap(gaps, seen_gap_keys, gap)

    for statement in future_work:
        gap = _gap_from_statements(
            "future_work",
            "A possible research gap is suggested by future-work evidence: "
            f"{_clean_gap_phrase(statement)}",
            [statement],
        )
        _append_gap(gaps, seen_gap_keys, gap)

    limitations_by_paper: dict[str, list[dict]] = defaultdict(list)
    for statement in limitations:
        limitations_by_paper[str(statement.get("paper_id", ""))].append(statement)

    for result in results:
        for limitation in limitations_by_paper.get(str(result.get("paper_id", "")), []):
            gap = _gap_from_statements(
                "result_with_limitation",
                "A result appears to need follow-up because it has a related limitation: "
                f"{_clean_gap_phrase(result)}; limitation: {_clean_gap_phrase(limitation)}",
                [result, limitation],
            )
            _append_gap(gaps, seen_gap_keys, gap)

    return gaps[:max_gaps]


def generate_hypotheses(
    gaps: list[dict],
    statements: list[dict],
    max_hypotheses: int = 10,
) -> list[dict]:
    """Generate cautious, testable hypotheses from evidence-backed gaps."""

    if max_hypotheses <= 0:
        raise ValueError("max_hypotheses must be greater than 0.")

    if not gaps:
        return []

    statement_lookup = {str(item.get("statement_id", "")): item for item in statements}
    hypotheses: list[dict] = []
    for gap in sorted(gaps, key=_gap_sort_key):
        source_ids = [
            statement_id
            for statement_id in gap.get("source_statement_ids", [])
            if statement_id in statement_lookup
        ]
        if not source_ids:
            continue

        hypothesis_text = (
            "A testable hypothesis could be that a targeted follow-up experiment addressing "
            f"gap {gap['gap_id']} will clarify whether the reported limitation changes under "
            "a controlled evaluation."
        )
        hypothesis = {
            "hypothesis_id": _stable_id("hyp", [str(gap["gap_id"]), *source_ids]),
            "gap_id": gap["gap_id"],
            "hypothesis_text": hypothesis_text,
            "rationale": (
                "This hypothesis is generated from local evidence linked to the gap and should "
                "be treated as a candidate for testing, not as a proven finding."
            ),
            "evidence_statement_ids": source_ids,
            "confidence_level": _confidence_for_gap(gap),
            "safety_label": "speculative_research_hypothesis",
        }
        hypotheses.append(hypothesis)
        if len(hypotheses) >= max_hypotheses:
            break

    return hypotheses


def generate_experiment_plan(hypothesis: dict) -> dict:
    """Generate a deterministic local experiment-plan skeleton for a hypothesis."""

    hypothesis_text = normalize_statement_text(str(hypothesis.get("hypothesis_text", "")))
    if not hypothesis.get("hypothesis_id") or not hypothesis_text:
        raise ValueError("hypothesis must include hypothesis_id and hypothesis_text.")

    return {
        "objective": f"Test the candidate hypothesis: {hypothesis_text}",
        "required_data": (
            "Use local, open-access or synthetic data linked to the source statements for "
            f"gap {hypothesis.get('gap_id', 'unknown')}."
        ),
        "method": (
            "Compare an intervention or analysis designed to address the gap against the "
            "current method or reported setup."
        ),
        "baseline_or_control": (
            "Use the original reported approach, dataset, or no-intervention condition as "
            "the baseline/control where available."
        ),
        "metrics": [
            "task-specific performance metric",
            "robustness or generalization metric",
            "evidence coverage against source statements",
        ],
        "expected_outcome": (
            "The hypothesis would be supported only if measured outcomes improve or clarify "
            "the limitation under a predefined evaluation protocol."
        ),
        "risks_and_limitations": (
            "This plan is speculative and may be limited by small samples, synthetic data, "
            "dataset shift, or incomplete source evidence."
        ),
    }


def _append_gap(gaps: list[dict], seen_gap_keys: set[tuple[str, tuple[str, ...]]], gap: dict) -> None:
    if not gap.get("source_statement_ids") or not gap.get("evidence_text"):
        return
    key = (
        str(gap.get("gap_type", "")),
        tuple(str(item) for item in gap.get("source_statement_ids", [])),
    )
    if key in seen_gap_keys:
        return
    seen_gap_keys.add(key)
    gaps.append(gap)


def _gap_from_statements(gap_type: str, gap_text: str, statements: list[dict]) -> dict:
    evidence_statements = [
        statement
        for statement in statements
        if statement.get("statement_id") and normalize_statement_text(str(statement.get("evidence_text", "")))
    ]
    source_ids = [str(statement["statement_id"]) for statement in evidence_statements]
    evidence_text = [
        _evidence_snippet(str(statement.get("evidence_text", "")))
        for statement in evidence_statements
    ]
    paper_ids = sorted({str(statement.get("paper_id", "")) for statement in evidence_statements})

    return {
        "gap_id": _stable_id("gap", [gap_type, *source_ids]),
        "gap_type": gap_type,
        "gap_text": normalize_statement_text(gap_text),
        "source_statement_ids": source_ids,
        "evidence_text": evidence_text,
        "paper_ids": paper_ids,
    }


def _clean_gap_phrase(statement: dict) -> str:
    text = normalize_statement_text(str(statement.get("statement_text", "")))
    return text[:240].rstrip()


def _confidence_for_gap(gap: dict) -> str:
    gap_type = gap.get("gap_type")
    evidence_count = len(gap.get("source_statement_ids", []))
    if gap_type == "result_with_limitation" and evidence_count >= 2:
        return "medium"
    return "low"


def _stable_id(prefix: str, parts: list[str]) -> str:
    digest_input = "|".join(normalize_statement_text(part) for part in parts)
    digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _evidence_snippet(text: str) -> str:
    normalized = normalize_statement_text(text)
    if len(normalized) <= MAX_GAP_EVIDENCE_CHARS:
        return normalized
    return normalized[: MAX_GAP_EVIDENCE_CHARS - 3].rstrip() + "..."


def _statement_sort_key(statement: dict) -> tuple[str, str, int, str]:
    return (
        str(statement.get("paper_id", "")),
        str(statement.get("chunk_id", "")),
        int(statement.get("sentence_index", 0)),
        str(statement.get("statement_id", "")),
    )


def _gap_sort_key(gap: dict) -> tuple[str, str]:
    return (
        str(gap.get("gap_id", "")),
        re.sub(r"\s+", " ", str(gap.get("gap_text", ""))).strip(),
    )
