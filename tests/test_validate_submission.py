import json
from pathlib import Path

from scripts.validate_submission import REQUIRED_FILES, validate_submission


README_SECTIONS = (
    "Project Summary\n"
    "Why This Is An Agent\n"
    "Capstone Evaluation Coverage\n"
    "Quickstart\n"
    "Architecture\n"
    "Security And Privacy\n"
    "Demo Workflow\n"
    "Demo Screenshots\n"
    "Repository Map\n"
    "Agent And MCP Commands\n"
)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_valid_agent_trace(root: Path) -> None:
    write_json(
        root / "data/generated/agent_trace_demo.json",
        {
            "steps": [
                {
                    "step_type": "planning",
                    "tool_name": "planned_tool_trajectory",
                    "purpose": "Plan.",
                    "input_summary": "Question.",
                    "output_summary": "Plan.",
                },
                {
                    "step_type": "ingestion",
                    "tool_name": "ingest_local_papers",
                    "purpose": "Ingest.",
                    "input_summary": "PDFs.",
                    "output_summary": "Statements.",
                },
                {
                    "step_type": "retrieval",
                    "tool_name": "search_local_corpus",
                    "purpose": "Search.",
                    "input_summary": "Query.",
                    "output_summary": "stmt_001.",
                },
                {
                    "step_type": "grounding",
                    "tool_name": "inspect_evidence",
                    "purpose": "Inspect.",
                    "input_summary": "stmt_001.",
                    "output_summary": "Evidence.",
                },
                {
                    "step_type": "safety_check",
                    "tool_name": "evaluate_local_outputs",
                    "purpose": "Evaluate.",
                    "input_summary": "Outputs.",
                    "output_summary": "Safe enough for review.",
                },
                {
                    "step_type": "final_answer",
                    "tool_name": "compose_grounded_answer",
                    "purpose": "Answer.",
                    "input_summary": "Evidence.",
                    "output_summary": "Answer references stmt_001.",
                },
            ],
            "final_answer": {
                "text": "Grounded answer references stmt_001.",
                "evidence_ids": ["stmt_001"],
            },
        },
    )


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
            path.write_text(README_SECTIONS, encoding="utf-8")
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
    write_valid_agent_trace(tmp_path)
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
            path.write_text(README_SECTIONS, encoding="utf-8")
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
    write_valid_agent_trace(tmp_path)
    monkeypatch.setattr(
        "scripts.validate_submission.calculate_project_stats",
        lambda db_path: {"papers": 5, "statements": 10, "graph_nodes": 20},
    )

    report = validate_submission(str(tmp_path))

    assert report["ready"] is True
    assert report["summary"]["failed"] == 0
