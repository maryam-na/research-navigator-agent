"""Configuration loading and validation for ResearchNavigator Agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tools.policy_tools import _parse_simple_yaml


DEFAULT_CONFIG_PATH = Path("configs/default.yaml")


@dataclass(frozen=True)
class PathConfig:
    papers_dir: str
    db_path: str
    graph_path: str
    discovery_path: str
    evaluation_path: str
    golden_eval_path: str
    brief_path: str
    sample_outputs_dir: str
    screenshots_dir: str


@dataclass(frozen=True)
class PipelineConfig:
    max_statements_per_type_per_paper: int
    max_gaps: int
    max_hypotheses: int
    max_graph_nodes: int
    allow_graph_truncate: bool


@dataclass(frozen=True)
class EvaluationConfig:
    min_overall_score: float
    min_golden_pass_rate: float


@dataclass(frozen=True)
class UiConfig:
    default_search_query: str
    max_search_results: int


@dataclass(frozen=True)
class ResearchNavigatorConfig:
    version: int
    paths: PathConfig
    pipeline: PipelineConfig
    evaluation: EvaluationConfig
    ui: UiConfig

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> ResearchNavigatorConfig:
    """Load and validate the local project configuration."""

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file does not exist: {config_path}")
    payload = _parse_simple_yaml(config_path.read_text(encoding="utf-8"))
    return parse_config(payload)


def parse_config(payload: dict[str, Any]) -> ResearchNavigatorConfig:
    """Parse a config dictionary into typed dataclasses."""

    version = _positive_int(payload.get("version"), "version")
    paths = payload.get("paths", {})
    pipeline = payload.get("pipeline", {})
    evaluation = payload.get("evaluation", {})
    ui = payload.get("ui", {})

    config = ResearchNavigatorConfig(
        version=version,
        paths=PathConfig(
            papers_dir=_required_str(paths, "papers_dir"),
            db_path=_required_str(paths, "db_path"),
            graph_path=_required_str(paths, "graph_path"),
            discovery_path=_required_str(paths, "discovery_path"),
            evaluation_path=_required_str(paths, "evaluation_path"),
            golden_eval_path=_required_str(paths, "golden_eval_path"),
            brief_path=_required_str(paths, "brief_path"),
            sample_outputs_dir=_required_str(paths, "sample_outputs_dir"),
            screenshots_dir=_required_str(paths, "screenshots_dir"),
        ),
        pipeline=PipelineConfig(
            max_statements_per_type_per_paper=_positive_int(
                pipeline.get("max_statements_per_type_per_paper"),
                "max_statements_per_type_per_paper",
            ),
            max_gaps=_positive_int(pipeline.get("max_gaps"), "max_gaps"),
            max_hypotheses=_positive_int(pipeline.get("max_hypotheses"), "max_hypotheses"),
            max_graph_nodes=_positive_int(pipeline.get("max_graph_nodes"), "max_graph_nodes"),
            allow_graph_truncate=_bool_value(
                pipeline.get("allow_graph_truncate"),
                "allow_graph_truncate",
            ),
        ),
        evaluation=EvaluationConfig(
            min_overall_score=_score_value(evaluation.get("min_overall_score"), "min_overall_score"),
            min_golden_pass_rate=_score_value(
                evaluation.get("min_golden_pass_rate"),
                "min_golden_pass_rate",
            ),
        ),
        ui=UiConfig(
            default_search_query=_required_str(ui, "default_search_query"),
            max_search_results=_positive_int(ui.get("max_search_results"), "max_search_results"),
        ),
    )
    return config


def _required_str(section: dict[str, Any], key: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Config value must be a non-empty string: {key}")
    return value.strip()


def _positive_int(value: Any, key: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Config value must be a positive integer: {key}") from exc
    if parsed <= 0:
        raise ValueError(f"Config value must be a positive integer: {key}")
    return parsed


def _score_value(value: Any, key: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Config value must be a score between 0 and 1: {key}") from exc
    if parsed < 0 or parsed > 1:
        raise ValueError(f"Config value must be a score between 0 and 1: {key}")
    return parsed


def _bool_value(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise ValueError(f"Config value must be boolean: {key}")
