"""Research gap, hypothesis, and experiment-plan schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ConfidenceLevel = Literal["low", "medium", "high"]


class ResearchGap(BaseModel):
    """Evidence-backed candidate research gap."""

    model_config = ConfigDict(extra="forbid")

    gap_id: str = Field(min_length=1)
    gap_type: str = Field(min_length=1)
    gap_text: str = Field(min_length=1)
    source_statement_ids: list[str] = Field(min_length=1)
    evidence_text: list[str] = Field(min_length=1)
    paper_ids: list[str] = Field(default_factory=list)

    @field_validator("source_statement_ids", "evidence_text", mode="after")
    @classmethod
    def no_blank_items(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("list must contain at least one non-empty item")
        return cleaned


class Hypothesis(BaseModel):
    """Speculative, evidence-linked hypothesis."""

    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str = Field(min_length=1)
    gap_id: str = Field(min_length=1)
    hypothesis_text: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    evidence_statement_ids: list[str] = Field(min_length=1)
    confidence_level: ConfidenceLevel
    safety_label: Literal["speculative_research_hypothesis"]

    @field_validator("hypothesis_text", mode="after")
    @classmethod
    def avoid_proven_discovery_language(cls, value: str) -> str:
        lowered = value.lower()
        if "proven" in lowered or "proves" in lowered:
            raise ValueError("hypothesis_text must not present speculation as proven")
        return value.strip()


class ExperimentPlan(BaseModel):
    """Experiment plan fields expected by the UI and evaluator."""

    model_config = ConfigDict(extra="forbid")

    objective: str = Field(min_length=1)
    required_data: str = Field(min_length=1)
    method: str = Field(min_length=1)
    baseline_or_control: str = Field(min_length=1)
    metrics: list[str] = Field(min_length=1)
    expected_outcome: str = Field(min_length=1)
    risks_and_limitations: str = Field(min_length=1)


class ExperimentPlanRecord(BaseModel):
    """Experiment plan linked to a hypothesis."""

    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str = Field(min_length=1)
    plan: ExperimentPlan


class DiscoveryCounts(BaseModel):
    """Counts included in discovery output files."""

    model_config = ConfigDict(extra="forbid")

    statements: int = Field(ge=0)
    gaps: int = Field(ge=0)
    hypotheses: int = Field(ge=0)
    experiment_plans: int = Field(ge=0)


class DiscoveryPayload(BaseModel):
    """Full gaps/hypotheses JSON payload."""

    model_config = ConfigDict(extra="forbid")

    counts: DiscoveryCounts
    gaps: list[ResearchGap]
    hypotheses: list[Hypothesis]
    experiment_plans: list[ExperimentPlanRecord]
