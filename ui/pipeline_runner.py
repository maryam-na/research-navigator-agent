"""Safe local pipeline runner helpers for the Streamlit UI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.run_demo import run_demo
from tools.config_tools import DEFAULT_CONFIG_PATH, ResearchNavigatorConfig, load_config
from ui.corpus_setup import CORPUS_MAX_PDFS, CORPUS_MIN_PDFS, describe_pdf_corpus

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ProgressCallback = Callable[[str, str], None]
PipelineRunner = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class LocalPipelineValidation:
    """Pre-run validation details for a local pipeline request."""

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    corpus: dict[str, Any] = field(default_factory=dict)
    pipeline_kwargs: dict[str, Any] = field(default_factory=dict)
    artifact_paths: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LocalPipelineRunResult:
    """Structured result suitable for Streamlit display and tests."""

    ok: bool
    message: str
    summary: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    corpus: dict[str, Any] = field(default_factory=dict)
    artifact_paths: dict[str, str] = field(default_factory=dict)


def validate_local_pipeline_config(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    workspace_root: str | Path = PROJECT_ROOT,
) -> LocalPipelineValidation:
    """Validate that the configured pipeline can run locally from the UI."""

    root = Path(workspace_root).expanduser().resolve(strict=False)
    try:
        config = load_config(config_path)
    except Exception as exc:
        return LocalPipelineValidation(
            ok=False,
            errors=[f"Unable to load local pipeline config: {exc}"],
        )

    path_result = _resolve_pipeline_paths(config, root)
    if path_result["errors"]:
        return LocalPipelineValidation(
            ok=False,
            errors=path_result["errors"],
            artifact_paths=path_result["artifact_paths"],
        )

    paths = path_result["paths"]
    manifest_path = paths["papers_dir"] / "manifest.json"
    corpus = describe_pdf_corpus(
        paths["papers_dir"],
        manifest_path,
        min_pdfs=CORPUS_MIN_PDFS,
        max_pdfs=CORPUS_MAX_PDFS,
    )
    errors: list[str] = []
    warnings: list[str] = []
    if corpus["status"] == "empty":
        errors.append("Add permitted local PDFs before running the pipeline.")
    elif corpus["status"] == "over_limit":
        errors.append(
            f"The local MVP limit is {CORPUS_MAX_PDFS} PDFs; remove PDFs before running."
        )
    elif corpus["status"] == "manifest_mismatch":
        errors.append("The paper manifest does not match data/papers; review Corpus Setup first.")
    elif corpus["status"] == "below_minimum":
        warnings.append(
            f"Found {corpus['pdf_count']} PDFs. The MVP target is "
            f"{CORPUS_MIN_PDFS}-{CORPUS_MAX_PDFS}; the run is useful for iteration, "
            "but add more permitted papers before a final demo."
        )

    pipeline_kwargs = {
        "papers_dir": str(paths["papers_dir"]),
        "db_path": str(paths["db_path"]),
        "graph_path": str(paths["graph_path"]),
        "discovery_path": str(paths["discovery_path"]),
        "evaluation_path": str(paths["evaluation_path"]),
        "brief_path": str(paths["brief_path"]),
        "max_statements_per_type_per_paper": (
            config.pipeline.max_statements_per_type_per_paper
        ),
        "max_gaps": config.pipeline.max_gaps,
        "max_hypotheses": config.pipeline.max_hypotheses,
    }
    return LocalPipelineValidation(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        corpus=corpus,
        pipeline_kwargs=pipeline_kwargs,
        artifact_paths=path_result["artifact_paths"],
    )


def run_local_pipeline(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    workspace_root: str | Path = PROJECT_ROOT,
    reset: bool = True,
    progress_callback: ProgressCallback | None = None,
    runner: PipelineRunner = run_demo,
) -> LocalPipelineRunResult:
    """Run the deterministic local pipeline without shelling out."""

    validation = validate_local_pipeline_config(config_path, workspace_root)
    if not validation.ok:
        return LocalPipelineRunResult(
            ok=False,
            message="Local pipeline was not started.",
            errors=validation.errors,
            warnings=validation.warnings,
            corpus=validation.corpus,
            artifact_paths=validation.artifact_paths,
        )

    try:
        summary = runner(
            **validation.pipeline_kwargs,
            reset=reset,
            progress_callback=progress_callback,
        )
    except Exception as exc:
        return LocalPipelineRunResult(
            ok=False,
            message="Local pipeline failed.",
            errors=[f"{exc.__class__.__name__}: {exc}"],
            warnings=validation.warnings,
            corpus=validation.corpus,
            artifact_paths=validation.artifact_paths,
        )

    return LocalPipelineRunResult(
        ok=True,
        message="Local pipeline completed and processed artifacts were regenerated.",
        summary=summary,
        warnings=validation.warnings,
        corpus=validation.corpus,
        artifact_paths=validation.artifact_paths,
    )


def _resolve_pipeline_paths(config: ResearchNavigatorConfig, root: Path) -> dict[str, Any]:
    raw_paths = {
        "papers_dir": config.paths.papers_dir,
        "db_path": config.paths.db_path,
        "graph_path": config.paths.graph_path,
        "discovery_path": config.paths.discovery_path,
        "evaluation_path": config.paths.evaluation_path,
        "brief_path": config.paths.brief_path,
    }
    paths: dict[str, Path] = {}
    errors: list[str] = []
    for label, value in raw_paths.items():
        resolved, error = _workspace_path(value, label, root)
        if error:
            errors.append(error)
        elif resolved is not None:
            paths[label] = resolved
    artifact_paths = {
        key: str(paths[key])
        for key in ("db_path", "graph_path", "discovery_path", "evaluation_path", "brief_path")
        if key in paths
    }
    return {"paths": paths, "errors": errors, "artifact_paths": artifact_paths}


def _workspace_path(value: str, label: str, root: Path) -> tuple[Path | None, str | None]:
    parsed = urlparse(value)
    if parsed.scheme and parsed.scheme != "file":
        return None, f"{label} must be a local workspace path, not a {parsed.scheme} URL."
    path_value = parsed.path if parsed.scheme == "file" else value
    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError:
        return None, f"{label} must stay inside the local project workspace."
    return resolved, None
