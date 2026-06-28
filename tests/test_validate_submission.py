import json
from pathlib import Path

from scripts.validate_submission import REQUIRED_FILES, validate_submission


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_validate_submission_flags_missing_project_files(tmp_path):
    report = validate_submission(str(tmp_path))

    assert report["ready"] is False
    assert report["summary"]["failed"] > 0


def test_validate_submission_checks_manifest_mismatch(tmp_path, monkeypatch):
    for required in REQUIRED_FILES:
        path = tmp_path / required
        path.parent.mkdir(parents=True, exist_ok=True)
        if required == "configs/default.yaml":
            path.write_text(Path(required).read_text(encoding="utf-8"), encoding="utf-8")
        else:
            path.write_text(
                "Competition Demo\nArchitecture\nADK Prototype Entry Point\nKnown Limitations\n",
                encoding="utf-8",
            )
    papers_dir = tmp_path / "data" / "papers"
    papers_dir.mkdir(parents=True)
    for index in range(5):
        (papers_dir / f"paper_{index}.pdf").write_text("pdf", encoding="utf-8")
    write_json(
        papers_dir / "manifest.json",
        {"papers": [{"filename": "paper_0.pdf"}]},
    )
    for artifact in [
        "data/processed/papers.sqlite",
        "data/processed/research_graph.graphml",
        "data/processed/gaps_and_hypotheses.json",
        "data/processed/researchnavigator_brief.md",
    ]:
        path = tmp_path / artifact
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("artifact", encoding="utf-8")
    write_json(
        tmp_path / "data/processed/evaluation_report.json",
        {"overall_score": 0.9, "failed_checks": [], "warnings": []},
    )
    write_json(
        tmp_path / "data/processed/golden_eval_report.json",
        {"pass_rate": 1.0, "failed_cases": 0},
    )
    monkeypatch.setattr(
        "scripts.validate_submission.calculate_project_stats",
        lambda db_path: {"papers": 5, "statements": 10, "graph_nodes": 20},
    )

    report = validate_submission(str(tmp_path))
    manifest_checks = [
        check for check in report["checks"] if check["category"] == "paper_manifest"
    ]

    assert report["ready"] is False
    assert manifest_checks[0]["status"] == "fail"


def test_validate_submission_passes_complete_fixture(tmp_path, monkeypatch):
    for required in REQUIRED_FILES:
        path = tmp_path / required
        path.parent.mkdir(parents=True, exist_ok=True)
        if required == "configs/default.yaml":
            path.write_text(Path(required).read_text(encoding="utf-8"), encoding="utf-8")
        else:
            path.write_text(
                "Competition Demo\nArchitecture\nADK Prototype Entry Point\nKnown Limitations\n",
                encoding="utf-8",
            )
    papers_dir = tmp_path / "data" / "papers"
    papers_dir.mkdir(parents=True)
    manifest_papers = []
    for index in range(5):
        filename = f"paper_{index}.pdf"
        (papers_dir / filename).write_text("pdf", encoding="utf-8")
        manifest_papers.append({"filename": filename})
    write_json(papers_dir / "manifest.json", {"papers": manifest_papers})
    for artifact in [
        "data/processed/papers.sqlite",
        "data/processed/research_graph.graphml",
        "data/processed/gaps_and_hypotheses.json",
        "data/processed/researchnavigator_brief.md",
    ]:
        path = tmp_path / artifact
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("artifact", encoding="utf-8")
    write_json(
        tmp_path / "data/processed/evaluation_report.json",
        {"overall_score": 0.9, "failed_checks": [], "warnings": []},
    )
    write_json(
        tmp_path / "data/processed/golden_eval_report.json",
        {"pass_rate": 1.0, "failed_cases": 0},
    )
    monkeypatch.setattr(
        "scripts.validate_submission.calculate_project_stats",
        lambda db_path: {"papers": 5, "statements": 10, "graph_nodes": 20},
    )

    report = validate_submission(str(tmp_path))

    assert report["ready"] is True
    assert report["summary"]["failed"] == 0
