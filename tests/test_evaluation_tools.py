from tools.evaluation_tools import (
    compute_grounding_score,
    compute_safety_score,
    compute_testability_score,
    compute_traceability_score,
    evaluate_outputs,
)


def sample_statements() -> list[dict]:
    return [{"statement_id": "stmt_001"}, {"statement_id": "stmt_002"}]


def sample_outputs() -> tuple[list[dict], list[dict], list[dict]]:
    gaps = [
        {
            "gap_id": "gap_001",
            "gap_text": "A possible research gap is suggested by a limitation.",
            "source_statement_ids": ["stmt_001"],
        }
    ]
    hypotheses = [
        {
            "hypothesis_id": "hyp_001",
            "gap_id": "gap_001",
            "hypothesis_text": "A testable hypothesis could be evaluated with local data.",
            "rationale": "Evidence-linked candidate.",
            "evidence_statement_ids": ["stmt_001"],
            "confidence_level": "low",
            "safety_label": "speculative_research_hypothesis",
        }
    ]
    plans = [
        {
            "hypothesis_id": "hyp_001",
            "plan": {
                "objective": "Test the candidate hypothesis.",
                "required_data": "Local synthetic data.",
                "method": "Compare intervention to baseline.",
                "baseline_or_control": "Original setup.",
                "metrics": ["accuracy"],
                "expected_outcome": "Clarifies the limitation.",
                "risks_and_limitations": "Small sample size.",
            },
        }
    ]
    return gaps, hypotheses, plans


def test_evaluate_outputs_returns_all_metrics():
    gaps, hypotheses, plans = sample_outputs()

    report = evaluate_outputs(gaps, hypotheses, plans, sample_statements())

    assert report["total_gaps"] == 1
    assert report["total_hypotheses"] == 1
    assert report["total_experiment_plans"] == 1
    assert 0.0 < report["overall_score"] < 1.0
    assert 0.0 < report["grounding_score"] < 1.0
    assert report["safety_score"] == 1.0
    assert 0.0 < report["testability_score"] <= 1.0
    assert report["traceability_score"] == 1.0
    assert report["metric_details"]["evaluated_output_count"] == 3
    assert report["warnings"]
    assert report["failed_checks"] == []


def test_compute_grounding_score_fails_missing_evidence():
    failed_checks = []
    score = compute_grounding_score(
        [{"gap_id": "gap_001", "source_statement_ids": ["missing"]}],
        [],
        sample_statements(),
        failed_checks,
    )

    assert score == 0.0
    assert failed_checks[0]["check"] == "grounding"


def test_compute_safety_score_flags_overclaiming_and_bad_hypothesis_label():
    failed_checks = []
    score = compute_safety_score(
        [],
        [
            {
                "hypothesis_id": "hyp_001",
                "hypothesis_text": "This proves and fully solves the problem.",
                "evidence_statement_ids": [],
                "safety_label": "grounded_fact",
            }
        ],
        [],
        failed_checks,
    )

    assert score == 0.0
    assert {item["check"] for item in failed_checks} == {"hypothesis_safety", "safety_text"}


def test_compute_testability_score_requires_plan_fields():
    failed_checks = []
    score = compute_testability_score(
        [{"hypothesis_id": "hyp_001", "hypothesis_text": "A testable hypothesis could be checked."}],
        [{"hypothesis_id": "hyp_001", "plan": {"objective": "Test it."}}],
        failed_checks,
    )

    assert 0.0 < score < 0.5
    assert failed_checks[0]["check"] == "testability"


def test_compute_traceability_score_requires_links():
    failed_checks = []
    score = compute_traceability_score(
        [{"gap_id": "gap_001", "source_statement_ids": []}],
        [{"hypothesis_id": "hyp_001", "gap_id": "missing", "evidence_statement_ids": ["stmt_001"]}],
        [{"hypothesis_id": "missing", "plan": {}}],
        failed_checks,
    )

    assert score == 0.0
    assert all(item["check"] == "traceability" for item in failed_checks)
