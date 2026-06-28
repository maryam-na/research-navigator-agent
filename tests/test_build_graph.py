from scripts import build_graph


def sample_statements() -> list[dict]:
    return [
        {
            "statement_id": "stmt_dataset",
            "paper_id": "paper_001",
            "chunk_id": "paper_001:chunk_0000",
            "statement_type": "dataset",
            "statement_text": "The benchmark dataset contains open research paper examples.",
            "evidence_text": "The benchmark dataset contains open research paper examples.",
            "confidence_rule": "rule:dataset",
            "sentence_index": 0,
        },
        {
            "statement_id": "stmt_method",
            "paper_id": "paper_001",
            "chunk_id": "paper_001:chunk_0000",
            "statement_type": "method",
            "statement_text": "We propose a local graph construction approach.",
            "evidence_text": "We propose a local graph construction approach.",
            "confidence_rule": "rule:we propose",
            "sentence_index": 1,
        },
        {
            "statement_id": "stmt_result",
            "paper_id": "paper_001",
            "chunk_id": "paper_001:chunk_0001",
            "statement_type": "result",
            "statement_text": "Results show that the graph remains deterministic.",
            "evidence_text": "Results show that the graph remains deterministic.",
            "confidence_rule": "rule:results show",
            "sentence_index": 0,
        },
    ]


def test_build_graph_warns_and_skips_export_when_over_max_nodes(tmp_path, monkeypatch, capsys):
    graph_path = tmp_path / "graph.graphml"
    monkeypatch.setattr(build_graph, "get_statements", lambda _db_path: sample_statements())

    summary = build_graph.build_graph_from_database(
        "unused.sqlite",
        str(graph_path),
        max_nodes=2,
    )

    assert summary["exported"] is False
    assert summary["truncated"] is False
    assert not graph_path.exists()
    assert "Use filtered statements during ingestion" in capsys.readouterr().err


def test_build_graph_allow_truncate_exports_bounded_graph(tmp_path, monkeypatch):
    graph_path = tmp_path / "graph.graphml"
    monkeypatch.setattr(build_graph, "get_statements", lambda _db_path: sample_statements())

    summary = build_graph.build_graph_from_database(
        "unused.sqlite",
        str(graph_path),
        max_nodes=2,
        allow_truncate=True,
    )

    assert summary["exported"] is True
    assert summary["truncated"] is True
    assert summary["nodes"] == 2
    assert graph_path.exists()

