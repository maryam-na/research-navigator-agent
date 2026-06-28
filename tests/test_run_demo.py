from scripts.ingest_papers import IngestionSummary
from scripts import run_demo as run_demo_module


def test_run_demo_composes_pipeline(monkeypatch, tmp_path):
    calls = []

    def fake_ingest(*args, **kwargs):
        calls.append(("ingest", args, kwargs))
        return IngestionSummary(papers=2, chunks=4, skipped_files=0, statements=6, raw_statements=8)

    def fake_graph(*args, **kwargs):
        calls.append(("graph", args, kwargs))
        return {"nodes": 10, "edges": 12, "exported": True, "truncated": False}

    def fake_discover(*args, **kwargs):
        calls.append(("discover", args, kwargs))
        return {"counts": {"statements": 6, "gaps": 3, "hypotheses": 2, "experiment_plans": 2}}

    def fake_evaluate(*args, **kwargs):
        calls.append(("evaluate", args, kwargs))
        return {
            "overall_score": 0.8,
            "grounding_score": 0.7,
            "safety_score": 1.0,
            "testability_score": 0.8,
            "traceability_score": 1.0,
            "warnings": [{"message": "narrow evidence"}],
            "failed_checks": [],
        }

    monkeypatch.setattr(run_demo_module, "ingest_papers", fake_ingest)
    monkeypatch.setattr(run_demo_module, "build_graph_from_database", fake_graph)
    monkeypatch.setattr(run_demo_module, "discover_from_database", fake_discover)
    monkeypatch.setattr(run_demo_module, "evaluate_from_files", fake_evaluate)
    monkeypatch.setattr(
        run_demo_module,
        "load_processed_data",
        lambda *args, **kwargs: {"statements": [], "gaps": [], "hypotheses": [], "graph": None},
    )
    monkeypatch.setattr(run_demo_module, "create_research_brief", lambda data: "# Brief\n")

    summary = run_demo_module.run_demo(
        papers_dir=str(tmp_path / "papers"),
        db_path=str(tmp_path / "processed" / "papers.sqlite"),
        graph_path=str(tmp_path / "processed" / "graph.graphml"),
        discovery_path=str(tmp_path / "processed" / "gaps.json"),
        evaluation_path=str(tmp_path / "processed" / "eval.json"),
        brief_path=str(tmp_path / "processed" / "brief.md"),
    )

    assert [call[0] for call in calls] == ["ingest", "graph", "discover", "evaluate"]
    assert summary["papers"] == 2
    assert summary["evaluation"]["overall_score"] == 0.8
    assert summary["evaluation"]["warnings"] == 1
    assert (tmp_path / "processed" / "brief.md").read_text(encoding="utf-8") == "# Brief\n"


def test_run_demo_reset_removes_existing_outputs(monkeypatch, tmp_path):
    processed = tmp_path / "processed"
    processed.mkdir()
    db_path = processed / "papers.sqlite"
    db_path.write_text("old", encoding="utf-8")

    def fake_ingest(*args, **kwargs):
        assert not db_path.exists()
        return IngestionSummary(papers=0, chunks=0, skipped_files=0, statements=0, raw_statements=0)

    monkeypatch.setattr(run_demo_module, "ingest_papers", fake_ingest)
    monkeypatch.setattr(
        run_demo_module,
        "build_graph_from_database",
        lambda *args, **kwargs: {"nodes": 0, "edges": 0, "exported": True, "truncated": False},
    )
    monkeypatch.setattr(
        run_demo_module,
        "discover_from_database",
        lambda *args, **kwargs: {"counts": {"statements": 0, "gaps": 0, "hypotheses": 0, "experiment_plans": 0}},
    )
    monkeypatch.setattr(
        run_demo_module,
        "evaluate_from_files",
        lambda *args, **kwargs: {
            "overall_score": 0.0,
            "grounding_score": 0.0,
            "safety_score": 0.0,
            "testability_score": 0.0,
            "traceability_score": 0.0,
            "warnings": [],
            "failed_checks": [],
        },
    )
    monkeypatch.setattr(
        run_demo_module,
        "load_processed_data",
        lambda *args, **kwargs: {"statements": [], "gaps": [], "hypotheses": [], "graph": None},
    )
    monkeypatch.setattr(run_demo_module, "create_research_brief", lambda data: "# Brief\n")

    run_demo_module.run_demo(
        papers_dir=str(tmp_path / "papers"),
        db_path=str(db_path),
        graph_path=str(processed / "graph.graphml"),
        discovery_path=str(processed / "gaps.json"),
        evaluation_path=str(processed / "eval.json"),
        brief_path=str(processed / "brief.md"),
        reset=True,
    )


def test_run_demo_rejects_invalid_statement_cap(tmp_path):
    try:
        run_demo_module.run_demo(
            papers_dir=str(tmp_path),
            db_path=str(tmp_path / "papers.sqlite"),
            max_statements_per_type_per_paper=0,
        )
    except ValueError as exc:
        assert "max_statements_per_type_per_paper" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
