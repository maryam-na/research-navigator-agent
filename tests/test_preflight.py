import json
from pathlib import Path

from scripts.preflight import run_preflight


def write_default_config(root: Path) -> None:
    config_path = root / "configs" / "default.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(Path("configs/default.yaml").read_text(encoding="utf-8"), encoding="utf-8")


def write_required_files(root: Path, files: tuple[str, ...]) -> None:
    for relative_path in files:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative_path == "configs/default.yaml":
            write_default_config(root)
        else:
            path.write_text("placeholder", encoding="utf-8")


def test_preflight_flags_missing_required_files(tmp_path):
    write_default_config(tmp_path)

    report = run_preflight(
        str(tmp_path),
        required_imports=("json",),
        required_project_files=("README.md", "configs/default.yaml"),
        processed_artifacts=(),
    )

    assert report["ready"] is False
    assert any(
        check["category"] == "project_file"
        and check["name"] == "README.md"
        and check["status"] == "fail"
        for check in report["checks"]
    )


def test_preflight_passes_minimal_project_without_requiring_artifacts(tmp_path):
    write_required_files(tmp_path, ("README.md", "configs/default.yaml"))

    report = run_preflight(
        str(tmp_path),
        required_imports=("json",),
        required_project_files=("README.md", "configs/default.yaml"),
        processed_artifacts=("data/processed/papers.sqlite",),
    )

    assert report["ready"] is True
    assert report["next_command"] == "make demo"
    assert any(check["status"] == "warn" for check in report["checks"])


def test_preflight_require_artifacts_fails_when_outputs_are_missing(tmp_path):
    write_required_files(tmp_path, ("README.md", "configs/default.yaml"))

    report = run_preflight(
        str(tmp_path),
        require_artifacts=True,
        required_imports=("json",),
        required_project_files=("README.md", "configs/default.yaml"),
        processed_artifacts=("data/processed/papers.sqlite",),
    )

    assert report["ready"] is False
    assert report["next_command"].startswith("Fix failed preflight")


def test_preflight_fails_invalid_existing_evaluation_report(tmp_path):
    write_required_files(tmp_path, ("README.md", "configs/default.yaml"))
    output_path = tmp_path / "data" / "processed" / "evaluation_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"overall_score": 2.0}), encoding="utf-8")

    report = run_preflight(
        str(tmp_path),
        required_imports=("json",),
        required_project_files=("README.md", "configs/default.yaml"),
        processed_artifacts=("data/processed/evaluation_report.json",),
    )

    assert report["ready"] is False
    assert any(
        check["category"] == "schema"
        and check["name"] == "data/processed/evaluation_report.json"
        and check["status"] == "fail"
        for check in report["checks"]
    )
