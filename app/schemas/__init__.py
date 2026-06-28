"""Typed data contracts for ResearchNavigator Agent."""

from app.schemas.discovery import (
    DiscoveryPayload,
    ExperimentPlan,
    ExperimentPlanRecord,
    Hypothesis,
    ResearchGap,
)
from app.schemas.evaluation import EvaluationReport, EvaluationWarning, MetricDetails
from app.schemas.paper import ChunkRecord, PaperRecord
from app.schemas.statement import StatementRecord, StatementType

__all__ = [
    "ChunkRecord",
    "DiscoveryPayload",
    "EvaluationReport",
    "EvaluationWarning",
    "ExperimentPlan",
    "ExperimentPlanRecord",
    "Hypothesis",
    "MetricDetails",
    "PaperRecord",
    "ResearchGap",
    "StatementRecord",
    "StatementType",
]
