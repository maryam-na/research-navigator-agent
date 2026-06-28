import pytest

from tools.extraction_tools import (
    classify_statement_type,
    deduplicate_statements,
    extract_research_statements,
    filter_statements,
    is_high_value_statement,
    normalize_statement_text,
    truncate_statement_text,
)


@pytest.mark.parametrize(
    ("sentence", "expected_type"),
    [
        ("We propose a graph-based denoising approach.", "method"),
        ("Results show that the model improves macro-F1.", "result"),
        ("A limitation is that the corpus is synthetic.", "limitation"),
        ("Future work should investigate real-world deployments.", "future_work"),
        ("The benchmark dataset contains 1,200 examples.", "dataset"),
        ("Prior work studies citation prediction.", "background"),
        ("The paper has three sections.", "unknown"),
    ],
)
def test_classify_statement_type_covers_all_types(sentence, expected_type):
    assert classify_statement_type(sentence) == expected_type


def test_classify_statement_type_uses_priority_order():
    sentence = "Future work is needed because the dataset does not include small cohorts."

    assert classify_statement_type(sentence) == "future_work"


def test_normalize_statement_text_collapses_whitespace():
    assert normalize_statement_text("  We   propose\n a method.  ") == "We propose a method."


def test_normalize_statement_text_requires_string():
    with pytest.raises(TypeError, match="text must be a string"):
        normalize_statement_text(None)  # type: ignore[arg-type]


def test_extract_research_statements_returns_grounded_dicts_with_stable_ids():
    text = (
        "We introduce a local extraction approach. "
        "It achieves higher recall on the benchmark dataset."
    )

    first = extract_research_statements(text, paper_id="paper_001", chunk_id="chunk_0000")
    second = extract_research_statements(text, paper_id="paper_001", chunk_id="chunk_0000")

    assert first == second
    assert [statement["statement_type"] for statement in first] == ["method", "result"]
    assert first[0]["statement_id"].startswith("stmt_")
    assert first[0]["paper_id"] == "paper_001"
    assert first[0]["chunk_id"] == "chunk_0000"
    assert first[0]["statement_text"] == "We introduce a local extraction approach."
    assert first[0]["evidence_text"] == "We introduce a local extraction approach."
    assert first[0]["confidence_rule"] == "rule:we introduce"
    assert first[0]["sentence_index"] == 0
    assert first[1]["sentence_index"] == 1


def test_extract_research_statements_deduplicates_and_bounds_text():
    long_sentence = "We propose a deterministic local method " + ("with repeated detail " * 80) + "."
    text = f"{long_sentence} {long_sentence}"

    statements = extract_research_statements(text, paper_id="paper_001", chunk_id="chunk_0000")

    assert len(statements) == 1
    assert len(statements[0]["statement_text"]) <= 500
    assert len(statements[0]["evidence_text"]) <= 320
    assert statements[0]["statement_text"].endswith("...")


def test_deduplicate_statements_removes_near_duplicates():
    statements = [
        statement(
            "stmt_a",
            "method",
            "We propose a deterministic local graph construction approach for papers.",
            sentence_index=0,
        ),
        statement(
            "stmt_b",
            "method",
            "We propose a deterministic local graph construction approach for research papers.",
            sentence_index=1,
        ),
    ]

    assert [item["statement_id"] for item in deduplicate_statements(statements)] == ["stmt_a"]


def test_truncate_statement_text_validates_length():
    with pytest.raises(ValueError, match="max_chars"):
        truncate_statement_text("abcdef", max_chars=3)


def test_extract_research_statements_rejects_missing_identifiers():
    with pytest.raises(ValueError, match="paper_id"):
        extract_research_statements("We propose a method.", paper_id="", chunk_id="chunk")

    with pytest.raises(ValueError, match="chunk_id"):
        extract_research_statements("We propose a method.", paper_id="paper", chunk_id="")


def statement(
    statement_id: str,
    statement_type: str,
    statement_text: str,
    confidence_rule: str = "rule:we propose",
    paper_id: str = "paper_001",
    sentence_index: int = 0,
) -> dict:
    return {
        "statement_id": statement_id,
        "paper_id": paper_id,
        "chunk_id": f"{paper_id}:chunk_0000",
        "statement_type": statement_type,
        "statement_text": statement_text,
        "evidence_text": statement_text,
        "confidence_rule": confidence_rule,
        "sentence_index": sentence_index,
    }


def test_is_high_value_statement_filters_common_noise():
    assert is_high_value_statement(
        statement(
            "stmt_good",
            "method",
            "We propose a deterministic local graph construction approach for papers.",
        )
    )
    assert not is_high_value_statement(
        statement("stmt_unknown", "unknown", "This sentence is long enough but has no useful rule.")
    )
    assert not is_high_value_statement(statement("stmt_short", "method", "We propose X."))
    assert not is_high_value_statement(
        statement(
            "stmt_ref",
            "background",
            "References Smith, A. and Jones, B. Research Systems, 2024.",
        )
    )
    assert not is_high_value_statement(
        statement(
            "stmt_url",
            "dataset",
            "The dataset is available at https://example.com/research/data/archive.",
        )
    )
    assert not is_high_value_statement(
        statement(
            "stmt_numbers",
            "result",
            "12345 67890 24680 13579 11223 44556 77889 99000.",
        )
    )


def test_filter_statements_excludes_unknown_by_default():
    statements = [
        statement(
            "stmt_method",
            "method",
            "We propose a deterministic local graph construction approach for papers.",
        ),
        statement(
            "stmt_unknown",
            "unknown",
            "This sentence is long enough but has no useful extraction rule.",
            confidence_rule="rule:no_rule_matched",
        ),
    ]

    filtered = filter_statements(statements)

    assert [item["statement_id"] for item in filtered] == ["stmt_method"]


def test_filter_statements_can_include_unknown():
    statements = [
        statement(
            "stmt_unknown",
            "unknown",
            "This sentence is long enough but has no useful extraction rule.",
            confidence_rule="rule:no_rule_matched",
        )
    ]

    assert [item["statement_id"] for item in filter_statements(statements, include_unknown=True)] == [
        "stmt_unknown"
    ]


def test_filter_statements_caps_per_type_per_paper_and_prefers_stronger_rules():
    statements = [
        statement(
            "stmt_weak",
            "method",
            "This approach creates a local graph from extracted paper statements.",
            confidence_rule="rule:approach",
            sentence_index=0,
        ),
        statement(
            "stmt_strong_1",
            "method",
            "We propose a deterministic graph construction method for extracted statements.",
            confidence_rule="rule:we propose",
            sentence_index=1,
        ),
        statement(
            "stmt_strong_2",
            "method",
            "We introduce a local graph quality control method for research papers.",
            confidence_rule="rule:we introduce",
            sentence_index=2,
        ),
        statement(
            "stmt_other_paper",
            "method",
            "This approach should remain because caps are scoped to each paper.",
            confidence_rule="rule:approach",
            paper_id="paper_002",
            sentence_index=0,
        ),
    ]

    filtered = filter_statements(statements, max_per_type_per_paper=2)

    assert [item["statement_id"] for item in filtered] == [
        "stmt_strong_1",
        "stmt_strong_2",
        "stmt_other_paper",
    ]


def test_filter_statements_rejects_invalid_cap():
    with pytest.raises(ValueError, match="max_per_type_per_paper"):
        filter_statements([], max_per_type_per_paper=0)
