from tools.gap_tools import (
    discover_research_gaps,
    generate_experiment_plan,
    generate_hypotheses,
)


def sample_statements() -> list[dict]:
    return [
        {
            "statement_id": "stmt_result",
            "paper_id": "paper_001",
            "chunk_id": "paper_001:chunk_0000",
            "statement_type": "result",
            "statement_text": "Results show that the model improves F1 on synthetic data.",
            "evidence_text": "Results show that the model improves F1 on synthetic data.",
            "confidence_rule": "rule:results show",
            "sentence_index": 0,
        },
        {
            "statement_id": "stmt_limitation",
            "paper_id": "paper_001",
            "chunk_id": "paper_001:chunk_0000",
            "statement_type": "limitation",
            "statement_text": "A limitation is that real-world behavior remains untested.",
            "evidence_text": "A limitation is that real-world behavior remains untested.",
            "confidence_rule": "rule:limitation",
            "sentence_index": 1,
        },
        {
            "statement_id": "stmt_future",
            "paper_id": "paper_001",
            "chunk_id": "paper_001:chunk_0001",
            "statement_type": "future_work",
            "statement_text": "Future work should investigate open field datasets.",
            "evidence_text": "Future work should investigate open field datasets.",
            "confidence_rule": "rule:future work",
            "sentence_index": 0,
        },
    ]


def test_gaps_require_evidence():
    statements = sample_statements() + [
        {
            "statement_id": "stmt_bad",
            "paper_id": "paper_002",
            "chunk_id": "paper_002:chunk_0000",
            "statement_type": "limitation",
            "statement_text": "A limitation is missing evidence text.",
            "evidence_text": "",
            "confidence_rule": "rule:limitation",
            "sentence_index": 0,
        }
    ]

    gaps = discover_research_gaps(statements)

    assert gaps
    assert all(gap["source_statement_ids"] for gap in gaps)
    assert all(gap["evidence_text"] for gap in gaps)
    assert "stmt_bad" not in {
        statement_id for gap in gaps for statement_id in gap["source_statement_ids"]
    }


def test_hypotheses_require_gaps():
    assert generate_hypotheses([], sample_statements()) == []


def test_hypotheses_have_safety_label_and_are_not_proven_discoveries():
    gaps = discover_research_gaps(sample_statements())
    hypotheses = generate_hypotheses(gaps, sample_statements())

    assert hypotheses
    assert all(hypothesis["gap_id"] for hypothesis in hypotheses)
    assert all(hypothesis["evidence_statement_ids"] for hypothesis in hypotheses)
    assert all(
        hypothesis["safety_label"] == "speculative_research_hypothesis"
        for hypothesis in hypotheses
    )
    assert all("proven" not in hypothesis["hypothesis_text"].lower() for hypothesis in hypotheses)
    assert all("testable hypothesis could be" in hypothesis["hypothesis_text"] for hypothesis in hypotheses)
    assert all("real-world behavior remains untested" not in hypothesis["hypothesis_text"] for hypothesis in hypotheses)


def test_gap_evidence_text_is_snippet_sized():
    long_text = "A limitation is that " + ("real-world field behavior remains untested " * 20)
    gaps = discover_research_gaps(
        [
            {
                "statement_id": "stmt_long_limitation",
                "paper_id": "paper_001",
                "chunk_id": "paper_001:chunk_0000",
                "statement_type": "limitation",
                "statement_text": long_text,
                "evidence_text": long_text,
                "confidence_rule": "rule:limitation",
                "sentence_index": 0,
            }
        ]
    )

    assert len(gaps[0]["evidence_text"][0]) <= 240
    assert gaps[0]["evidence_text"][0].endswith("...")


def test_experiment_plan_contains_required_fields():
    gaps = discover_research_gaps(sample_statements())
    hypothesis = generate_hypotheses(gaps, sample_statements(), max_hypotheses=1)[0]

    plan = generate_experiment_plan(hypothesis)

    assert set(plan) == {
        "objective",
        "required_data",
        "method",
        "baseline_or_control",
        "metrics",
        "expected_outcome",
        "risks_and_limitations",
    }
    assert plan["metrics"]


def test_gap_and_hypothesis_output_is_deterministic():
    first_gaps = discover_research_gaps(sample_statements(), max_gaps=3)
    second_gaps = discover_research_gaps(list(reversed(sample_statements())), max_gaps=3)

    assert first_gaps == second_gaps
    assert generate_hypotheses(first_gaps, sample_statements()) == generate_hypotheses(
        second_gaps,
        list(reversed(sample_statements())),
    )
