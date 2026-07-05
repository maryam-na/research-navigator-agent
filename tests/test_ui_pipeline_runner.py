import json
from pathlib import Path

from ui.pipeline_runner import (
    reset_local_demo_outputs,
    run_local_pipeline,
    validate_local_pipeline_config,
)


def write_config(root: Path, **path_overrides: str) -> Path:
    paths = {
        "papers_dir": "data/papers",
        "db_path": "data/processed/papers.sqlite",
        "graph_path": "data/processed/research_graph.graphml",
        "discovery_path": "data/processed/gaps_and_hypotheses.json",
        "evaluation_path": "data/processed/evaluation_report.json",
        "golden_eval_path": "data/processed/golden_eval_report.json",
        "brief_path": "data/processed/researchnavigator_brief.md",
        "sample_outputs_dir": "docs/sample_outputs",
        "screenshots_dir": "docs/screenshots",
        **path_overrides,
    }
    config_path = root / "configs" / "default.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        f"""
version: 1
paths:
  papers_dir: {paths["papers_dir"]}
  db_path: {paths["db_path"]}
  graph_path: {paths["graph_path"]}
  discovery_path: {paths["discovery_path"]}
  evaluation_path: {paths["evaluation_path"]}
  golden_eval_path: {paths["golden_eval_path"]}
  brief_path: {paths["brief_path"]}
  sample_outputs_dir: {paths["sample_outputs_dir"]}
  screenshots_dir: {paths["screenshots_dir"]}
pipeline:
  max_statements_per_type_per_paper: 30
  max_gaps: 10
  max_hypotheses: 10
  max_graph_nodes: 3000
  allow_graph_truncate: false
evaluation:
  min_overall_score: 0.75
  min_golden_pass_rate: 1.0
ui:
  default_search_query: limitations evaluation dataset
  max_search_results: 30
""",
        encoding="utf-8",
    )
    return config_path


def write_corpus(
    root: Path,
    filenames: list[str],
    manifest_filenames: list[str] | None = None,
) -> None:
    papers_dir = root / "data" / "papers"
    papers_dir.mkdir(parents=True)
    for filename in filenames:
        (papers_dir / filename).write_bytes(b"%PDF-1.4\n%%EOF\n")
    manifest_names = manifest_filenames if manifest_filenames is not None else filenames
    manifest = {
        "corpus_scope": "test corpus",
        "license_requirement": "Use only permitted papers.",
        "papers": [
            {
                "filename": filename,
                "paper_id": Path(filename).stem,
                "title": Path(filename).stem,
                "permission_confirmed": True,
            }
            for filename in manifest_names
        ],
    }
    (papers_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_validate_local_pipeline_config_accepts_ready_corpus(tmp_path):
    config_path = write_config(tmp_path)
    write_corpus(tmp_path, [f"paper_{index}.pdf" for index in range(5)])

    validation = validate_local_pipeline_config(config_path, workspace_root=tmp_path)

    assert validation.ok is True
    assert validation.errors == []
    assert validation.warnings == []
    assert validation.corpus["status"] == "ready"
    assert validation.pipeline_kwargs["papers_dir"] == str((tmp_path / "data/papers").resolve())


def test_validate_local_pipeline_config_warns_for_below_target_corpus(tmp_path):
    config_path = write_config(tmp_path)
    write_corpus(tmp_path, ["paper_a.pdf", "paper_b.pdf"])

    validation = validate_local_pipeline_config(config_path, workspace_root=tmp_path)

    assert validation.ok is True
    assert validation.corpus["status"] == "below_minimum"
    assert "MVP target is 5-10" in validation.warnings[0]


def test_validate_local_pipeline_config_blocks_manifest_mismatch(tmp_path):
    config_path = write_config(tmp_path)
    write_corpus(
        tmp_path,
        [f"paper_{index}.pdf" for index in range(5)],
        manifest_filenames=["paper_0.pdf"],
    )

    validation = validate_local_pipeline_config(config_path, workspace_root=tmp_path)

    assert validation.ok is False
    assert validation.corpus["status"] == "manifest_mismatch"
    assert "manifest does not match" in validation.errors[0]


def test_validate_local_pipeline_config_blocks_remote_or_outside_paths(tmp_path):
    config_path = write_config(tmp_path, db_path="https://example.com/papers.sqlite")
    write_corpus(tmp_path, [f"paper_{index}.pdf" for index in range(5)])

    validation = validate_local_pipeline_config(config_path, workspace_root=tmp_path)

    assert validation.ok is False
    assert "local workspace path" in validation.errors[0]


def test_run_local_pipeline_calls_existing_runner_with_configured_paths(tmp_path):
    config_path = write_config(tmp_path)
    write_corpus(tmp_path, [f"paper_{index}.pdf" for index in range(5)])
    calls = {}
    events = []

    def fake_runner(**kwargs):
        calls.update(kwargs)
        kwargs["progress_callback"]("fake_stage", "Fake progress")
        return {
            "papers": 5,
            "saved_statements": 12,
            "graph": {"nodes": 8},
            "discovery_counts": {"gaps": 2, "hypotheses": 2},
            "evaluation": {"overall_score": 1.0},
        }

    result = run_local_pipeline(
        config_path,
        workspace_root=tmp_path,
        reset=False,
        progress_callback=lambda stage, message: events.append((stage, message)),
        runner=fake_runner,
    )

    assert result.ok is True
    assert result.summary["papers"] == 5
    assert calls["reset"] is False
    assert calls["papers_dir"] == str((tmp_path / "data/papers").resolve())
    assert events == [("fake_stage", "Fake progress")]


def test_run_local_pipeline_reports_runner_failure(tmp_path):
    config_path = write_config(tmp_path)
    write_corpus(tmp_path, [f"paper_{index}.pdf" for index in range(5)])

    def failing_runner(**_kwargs):
        raise RuntimeError("pipeline broke")

    result = run_local_pipeline(config_path, workspace_root=tmp_path, runner=failing_runner)

    assert result.ok is False
    assert result.message == "Local pipeline failed."
    assert result.errors == ["RuntimeError: pipeline broke"]


def test_reset_local_demo_outputs_removes_generated_artifacts_only(tmp_path):
    config_path = write_config(tmp_path)
    write_corpus(tmp_path, [f"paper_{index}.pdf" for index in range(5)])
    artifact_paths = [
        tmp_path / "data/processed/papers.sqlite",
        tmp_path / "data/processed/research_graph.graphml",
        tmp_path / "data/processed/gaps_and_hypotheses.json",
        tmp_path / "data/processed/evaluation_report.json",
        tmp_path / "data/processed/researchnavigator_brief.md",
    ]
    for artifact_path in artifact_paths:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("generated", encoding="utf-8")
    pdf_path = tmp_path / "data/papers/paper_0.pdf"

    result = reset_local_demo_outputs(config_path, workspace_root=tmp_path)

    assert result.ok is True
    assert "Local PDFs were left unchanged" in result.message
    assert sorted(result.removed_artifacts) == sorted(
        str(path.resolve()) for path in artifact_paths
    )
    assert result.missing_artifacts == []
    assert all(not path.exists() for path in artifact_paths)
    assert pdf_path.exists()


def test_reset_local_demo_outputs_blocks_paths_outside_workspace(tmp_path):
    config_path = write_config(tmp_path, db_path="../outside.sqlite")

    result = reset_local_demo_outputs(config_path, workspace_root=tmp_path)

    assert result.ok is False
    assert result.message == "Demo outputs were not reset."
    assert "must stay inside the local project workspace" in result.errors[0]
