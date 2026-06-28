"""Evaluation report schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EvaluationWarning(BaseModel):
    """Warning emitted by deterministic evaluation."""

    model_config = ConfigDict(extra="allow")

    level: Literal["info", "warning", "error"] = "info"
    message: str = Field(min_length=1)


class MetricDetails(BaseModel):
    """Detailed evaluation metrics."""

    model_config = ConfigDict(extra="allow")

    evaluated_output_count: int = Field(ge=0)
    statement_count: int = Field(ge=0)
    paper_count: int = Field(ge=0)
    unique_evidence_statement_count: int = Field(ge=0)
    missing_evidence_statement_count: int = Field(ge=0)
    evidence_paper_count: int = Field(ge=0)
    average_evidence_per_gap: float = Field(ge=0)
    average_evidence_per_hypothesis: float = Field(ge=0)
    plan_specificity_score: float = Field(ge=0, le=1)
    warnings: list[EvaluationWarning] = Field(default_factory=list)


class EvaluationReport(BaseModel):
    """Evaluation report produced by tools.evaluation_tools."""

    model_config = ConfigDict(extra="forbid")

    total_gaps: int = Field(ge=0)
    total_hypotheses: int = Field(ge=0)
    total_experiment_plans: int = Field(ge=0)
    total_evaluated_items: int = Field(ge=0)
    overall_score: float = Field(ge=0, le=1)
    grounding_score: float = Field(ge=0, le=1)
    safety_score: float = Field(ge=0, le=1)
    testability_score: float = Field(ge=0, le=1)
    traceability_score: float = Field(ge=0, le=1)
    metric_details: MetricDetails
    warnings: list[EvaluationWarning] = Field(default_factory=list)
    failed_checks: list[dict[str, Any]] = Field(default_factory=list)
