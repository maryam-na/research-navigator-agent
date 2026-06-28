"""Deterministic rule-based extraction of research statements from text chunks."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict

MAX_STATEMENT_TEXT_CHARS = 500
MAX_EVIDENCE_TEXT_CHARS = 320

RULE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("future_work", ("future work", "we plan", "should investigate", "further research")),
    ("limitation", ("limitation", "limited by", "does not", "cannot", "future work is needed")),
    ("result", ("we show", "results show", "improves", "outperforms", "achieves", "reduces")),
    ("method", ("we propose", "we introduce", "we evaluate", "we use", "our method", "method", "approach")),
    ("dataset", ("dataset", "benchmark", "corpus", "cohort", "data")),
    ("background", ("prior work", "previous studies", "background", "related work")),
)

ALLOWED_STATEMENT_TYPES = {
    "method",
    "result",
    "limitation",
    "future_work",
    "dataset",
    "background",
    "unknown",
}

STRONG_CONFIDENCE_RULES = {
    "rule:we propose": 5,
    "rule:we introduce": 5,
    "rule:we show": 5,
    "rule:results show": 5,
    "rule:future work": 5,
    "rule:we plan": 5,
    "rule:should investigate": 5,
    "rule:further research": 5,
    "rule:limitation": 5,
    "rule:improves": 4,
    "rule:outperforms": 4,
    "rule:achieves": 4,
    "rule:reduces": 4,
    "rule:limited by": 4,
    "rule:does not": 4,
    "rule:cannot": 4,
    "rule:future work is needed": 4,
    "rule:dataset": 3,
    "rule:benchmark": 3,
    "rule:corpus": 3,
    "rule:cohort": 3,
    "rule:we use": 3,
    "rule:we evaluate": 3,
    "rule:our method": 3,
    "rule:method": 3,
    "rule:approach": 2,
    "rule:data": 2,
    "rule:prior work": 2,
    "rule:previous studies": 2,
    "rule:background": 2,
    "rule:related work": 2,
    "rule:no_rule_matched": 0,
}


def normalize_statement_text(text: str) -> str:
    """Normalize statement text without changing its meaning."""

    if not isinstance(text, str):
        raise TypeError("text must be a string.")
    return re.sub(r"\s+", " ", text).strip()


def truncate_statement_text(text: str, max_chars: int = MAX_STATEMENT_TEXT_CHARS) -> str:
    """Return a deterministic bounded-length statement text value."""

    normalized = normalize_statement_text(text)
    if max_chars <= 3:
        raise ValueError("max_chars must be greater than 3.")
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _split_sentences(text: str) -> list[str]:
    normalized = normalize_statement_text(text)
    if not normalized:
        return []
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized)
        if sentence.strip()
    ]


def _matching_rule(sentence: str) -> tuple[str, str]:
    lower_sentence = sentence.lower()
    for statement_type, patterns in RULE_PATTERNS:
        for pattern in patterns:
            if pattern in lower_sentence:
                return statement_type, pattern
    return "unknown", "no_rule_matched"


def classify_statement_type(sentence: str) -> str:
    """Classify a sentence into a research statement type using local rules."""

    normalized = normalize_statement_text(sentence)
    if not normalized:
        return "unknown"
    statement_type, _pattern = _matching_rule(normalized)
    return statement_type


def _statement_id(
    paper_id: str,
    chunk_id: str,
    sentence_index: int,
    statement_type: str,
    statement_text: str,
) -> str:
    digest_input = f"{paper_id}|{chunk_id}|{sentence_index}|{statement_type}|{statement_text}"
    digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:12]
    return f"stmt_{digest}"


def extract_research_statements(text: str, paper_id: str, chunk_id: str) -> list[dict]:
    """Extract rule-based research statements from a chunk of text."""

    if not paper_id or not paper_id.strip():
        raise ValueError("paper_id must be a non-empty string.")
    if not chunk_id or not chunk_id.strip():
        raise ValueError("chunk_id must be a non-empty string.")

    statements: list[dict] = []
    for sentence_index, sentence in enumerate(_split_sentences(text)):
        statement_text = truncate_statement_text(sentence)
        evidence_text = truncate_statement_text(sentence, max_chars=MAX_EVIDENCE_TEXT_CHARS)
        statement_type, pattern = _matching_rule(statement_text)
        statements.append(
            {
                "statement_id": _statement_id(
                    paper_id.strip(),
                    chunk_id.strip(),
                    sentence_index,
                    statement_type,
                    statement_text,
                ),
                "paper_id": paper_id.strip(),
                "chunk_id": chunk_id.strip(),
                "statement_type": statement_type,
                "statement_text": statement_text,
                "evidence_text": evidence_text,
                "confidence_rule": f"rule:{pattern}",
                "sentence_index": sentence_index,
            }
        )

    return deduplicate_statements(statements)


def deduplicate_statements(statements: list[dict]) -> list[dict]:
    """Remove duplicate and near-duplicate statements deterministically."""

    seen_exact: set[tuple[str, str, str, str]] = set()
    canonical_by_group: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    deduplicated: list[dict] = []

    for statement in sorted(statements, key=_statement_sort_key_for_dedup):
        statement_type = str(statement.get("statement_type", "unknown")).strip()
        paper_id = str(statement.get("paper_id", "")).strip()
        chunk_id = str(statement.get("chunk_id", "")).strip()
        text = truncate_statement_text(str(statement.get("statement_text", "")))
        canonical = _canonical_statement_text(text)
        if not canonical:
            continue

        exact_key = (paper_id, chunk_id, statement_type, canonical)
        if exact_key in seen_exact:
            continue

        group_key = (paper_id, statement_type, _canonical_prefix(canonical))
        if any(_near_duplicate(canonical, existing) for existing in canonical_by_group[group_key]):
            continue

        seen_exact.add(exact_key)
        canonical_by_group[group_key].append(canonical)
        cleaned = dict(statement)
        cleaned["statement_text"] = text
        cleaned["evidence_text"] = truncate_statement_text(
            str(statement.get("evidence_text", text)),
            max_chars=MAX_EVIDENCE_TEXT_CHARS,
        )
        deduplicated.append(cleaned)

    return sorted(deduplicated, key=_statement_sort_key_for_dedup)


def is_high_value_statement(statement: dict) -> bool:
    """Return whether a statement is useful enough for the MVP graph by default."""

    return _passes_quality_rules(statement, include_unknown=False)


def filter_statements(
    statements: list[dict],
    include_unknown: bool = False,
    max_per_type_per_paper: int = 50,
) -> list[dict]:
    """Filter and cap extracted statements deterministically for graph construction."""

    if max_per_type_per_paper <= 0:
        raise ValueError("max_per_type_per_paper must be greater than 0.")

    deduplicated_statements = deduplicate_statements(statements)
    grouped: dict[tuple[str, str], list[tuple[int, dict]]] = defaultdict(list)
    for original_index, statement in enumerate(deduplicated_statements):
        if not _passes_quality_rules(statement, include_unknown=include_unknown):
            continue
        key = (
            str(statement.get("paper_id", "")).strip(),
            str(statement.get("statement_type", "unknown")).strip(),
        )
        grouped[key].append((original_index, statement))

    selected_indices: set[int] = set()
    for _key, indexed_statements in grouped.items():
        ranked = sorted(
            indexed_statements,
            key=lambda item: (
                -_confidence_score(item[1]),
                str(item[1].get("paper_id", "")),
                str(item[1].get("chunk_id", "")),
                int(item[1].get("sentence_index", 0)),
                str(item[1].get("statement_id", "")),
            ),
        )
        selected_indices.update(index for index, _statement in ranked[:max_per_type_per_paper])

    return [
        statement
        for original_index, statement in enumerate(deduplicated_statements)
        if original_index in selected_indices
    ]


def _passes_quality_rules(statement: dict, include_unknown: bool) -> bool:
    statement_type = str(statement.get("statement_type", "unknown")).strip()
    if statement_type not in ALLOWED_STATEMENT_TYPES:
        return False
    if statement_type == "unknown" and not include_unknown:
        return False

    text = normalize_statement_text(str(statement.get("statement_text", "")))
    if len(text) < 40:
        return False
    if _looks_like_reference(text):
        return False
    if _looks_mostly_like_noise(text):
        return False
    return True


def _confidence_score(statement: dict) -> int:
    return STRONG_CONFIDENCE_RULES.get(
        normalize_statement_text(str(statement.get("confidence_rule", ""))).lower(),
        1,
    )


def _looks_like_reference(text: str) -> bool:
    lower_text = text.lower().strip()
    if lower_text in {"references", "bibliography", "works cited"}:
        return True
    if lower_text.startswith(("references ", "bibliography ", "doi:", "http://", "https://")):
        return True
    if re.match(r"^\[\d+\]\s+", text):
        return True
    if re.match(r"^\d+\.\s+[A-Z][A-Za-z-]+,\s+[A-Z]", text):
        return True
    if re.search(r"\bdoi\s*[:/]", lower_text):
        return True
    return False


def _looks_mostly_like_noise(text: str) -> bool:
    if re.search(r"https?://|www\.", text, flags=re.IGNORECASE):
        return True

    without_citations = re.sub(r"\[[\d,\s;-]+\]", " ", text)
    without_citations = re.sub(r"\([A-Z][A-Za-z-]+(?: et al\.)?,? \d{4}[a-z]?\)", " ", without_citations)
    citation_removed_chars = len(text) - len(without_citations)
    if len(text) > 0 and citation_removed_chars / len(text) > 0.35:
        return True

    alpha_chars = sum(1 for char in text if char.isalpha())
    numeric_chars = sum(1 for char in text if char.isdigit())
    if numeric_chars > alpha_chars:
        return True

    tokens = re.findall(r"\b[\w./:-]+\b", text)
    if not tokens:
        return True
    alpha_tokens = [token for token in tokens if re.search(r"[A-Za-z]", token)]
    return len(alpha_tokens) / len(tokens) < 0.45


def _canonical_statement_text(text: str) -> str:
    lowered = normalize_statement_text(text).lower()
    lowered = re.sub(r"\[[\d,\s;-]+\]", " ", lowered)
    lowered = re.sub(r"\([a-z][a-z-]+(?: et al\.)?,? \d{4}[a-z]?\)", " ", lowered)
    lowered = re.sub(r"https?://\S+|www\.\S+", " ", lowered)
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def _canonical_prefix(canonical: str) -> str:
    return " ".join(canonical.split()[:8])


def _near_duplicate(left: str, right: str) -> bool:
    if left == right:
        return True
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens)
    smaller = min(len(left_tokens), len(right_tokens))
    return overlap / smaller >= 0.85


def _statement_sort_key_for_dedup(statement: dict) -> tuple[str, str, int, str]:
    return (
        str(statement.get("paper_id", "")),
        str(statement.get("chunk_id", "")),
        int(statement.get("sentence_index", 0)),
        str(statement.get("statement_id", "")),
    )
