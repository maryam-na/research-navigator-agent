import json

import pytest
from pydantic import ValidationError

from app.schemas import (
    ChunkRecord,
    DiscoveryPayload,
    EvaluationReport,
    ExperimentPlan,
    ExperimentPlanRecord,
    Hypothesis,
    PaperRecord,
    ResearchGap,
    StatementRecord,
)


def test_paper_and_chunk_schema_validate_storage_records():
    paper = PaperRecord(
        paper_id="paper_001",
        title="Synthetic Paper",
        source_path="data/papers/paper_001.pdf",
        year=2026,
    )
    chunk = ChunkRecord(
        chunk_id="paper_001:chunk_0000",
        paper_id=paper.paper_id,
        chunk_index=0,
        text="Chunk text",
        start_char=0,
        end_char=10,
    )

    assert paper.paper_id == "paper_001"
    assert chunk.end_char == 10


def test_chunk_schema_rejects_invalid_span():
    with pytest.raises(ValidationError):
        ChunkRecord(
            chunk_id="chunk_001",
            paper_id="paper_001",
            chunk_index=0,
            text="Chunk",
            start_char=10,
            end_char=5,
        )


def test_statement_schema_rejects_invalid_type():
    with pytest.raises(ValidationError):
        StatementRecord(
            statement_id="stmt_001",
            paper_id="paper_001",
            chunk_id="chunk_001",
            statement_type="claim",
            statement_text="This is an unsupported type.",
            evidence_text="This is an unsupported type.",
            confidence_rule="rule:test",
        )


def test_discovery_schemas_require_grounding_and_speculative_label():
    gap = ResearchGap(
        gap_id="gap_001",
        gap_type="limitation",
        gap_text="A possible gap exists.",
        source_statement_ids=["stmt_001"],
        evidence_text=["A limitation is reported."],
        paper_ids=["paper_001"],
    )
    hypothesis = Hypothesis(
        hypothesis_id="hyp_001",
        gap_id=gap.gap_id,
        hypothesis_text="A testable hypothesis could clarify the limitation.",
        rationale="Evidence-linked candidate.",
        evidence_statement_ids=["stmt_001"],
        confidence_level="low",
        safety_label="speculative_research_hypothesis",
    )
    plan = ExperimentPlan(
        objective="Test the candidate hypothesis.",
        required_data="Local data.",
        method="Compare intervention to baseline.",
        baseline_or_control="Original setup.",
        metrics=["accuracy"],
        expected_outcome="Clarifies the limitation.",
        risks_and_limitations="Small sample.",
    )
    payload = DiscoveryPayload(
        counts={
            "statements": 1,
            "gaps": 1,
            "hypotheses": 1,
            "experiment_plans": 1,
        },
        gaps=[gap],
        hypotheses=[hypothesis],
        experiment_plans=[ExperimentPlanRecord(hypothesis_id="hyp_001", plan=plan)],
    )

    assert payload.counts.gaps == 1


def test_hypothesis_schema_rejects_proven_language():
    with pytest.raises(ValidationError):
        Hypothesis(
            hypothesis_id="hyp_001",
            gap_id="gap_001",
            hypothesis_text="This hypothesis is proven.",
            rationale="Bad certainty.",
            evidence_statement_ids=["stmt_001"],
            confidence_level="low",
            safety_label="speculative_research_hypothesis",
        )


def test_evaluation_report_schema_accepts_current_report():
    with open("data/processed/evaluation_report.json", encoding="utf-8") as file:
        payload = json.load(file)

    report = EvaluationReport.model_validate(payload)

    assert report.overall_score >= 0
    assert report.metric_details.paper_count >= 1
