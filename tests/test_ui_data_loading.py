import json

import networkx as nx

from tools.graph_tools import export_graphml
from tools.storage_tools import initialize_database, save_chunk, save_paper, save_statement
from ui.streamlit_app import (
    _available_statement_ids,
    _evaluation_caveat_items,
    _evidence_statement_ids_for_result,
    _render_dataframe,
    _render_plotly_chart,
    _statement_option_label,
    _subgraph_for_results,
    build_small_subgraph,
    dashboard_counts,
    evaluation_status_summary,
    file_presence,
    graph_to_tables,
    load_graph,
    load_json_file,
    load_processed_data,
    summarize_graph_from_path,
)


def create_sample_db(db_path):
    initialize_database(str(db_path))
    save_paper(str(db_path), "paper_001", "Synthetic Paper", "paper.pdf")
    save_chunk(str(db_path), "paper_001", "paper_001:chunk_0000", 0, "chunk text", 0, 10)
    save_statement(
        str(db_path),
        "stmt_001",
        "paper_001",
        "paper_001:chunk_0000",
        "method",
        "We propose a deterministic local graph construction approach.",
        "We propose a deterministic local graph construction approach.",
        "rule:we propose",
    )


def test_load_processed_data_returns_expected_tables(tmp_path):
    db_path = tmp_path / "papers.sqlite"
    create_sample_db(db_path)

    data = load_processed_data(db_path)

    assert len(data["papers"]) == 1
    assert len(data["chunks"]) == 1
    assert len(data["statements"]) == 1
    assert data["statements"].iloc[0]["statement_type"] == "method"


def test_load_helpers_handle_missing_files(tmp_path):
    missing_db = tmp_path / "missing.sqlite"
    missing_json = tmp_path / "missing.json"
    missing_graph = tmp_path / "missing.graphml"

    assert load_processed_data(missing_db)["papers"].empty
    assert load_json_file(missing_json) == {}
    assert load_graph(missing_graph).number_of_nodes() == 0


def test_graph_loading_summary_and_tables(tmp_path):
    graph = nx.DiGraph()
    graph.add_node("paper:paper_001", node_type="paper")
    graph.add_node("statement:stmt_001", node_type="statement")
    graph.add_edge("paper:paper_001", "statement:stmt_001", relation="contains")
    graph_path = tmp_path / "graph.graphml"
    export_graphml(graph, str(graph_path))

    loaded_graph = load_graph(graph_path)
    nodes_df, edges_df = graph_to_tables(loaded_graph)

    assert summarize_graph_from_path(graph_path)["nodes"] == 2
    assert len(build_small_subgraph(loaded_graph, max_nodes=1).nodes) == 1
    assert len(nodes_df) == 2
    assert len(edges_df) == 1


def test_overview_subgraph_prefers_connected_edges():
    graph = nx.DiGraph()
    graph.add_node("dataset:orphan_001", node_type="dataset")
    graph.add_node("dataset:orphan_002", node_type="dataset")
    graph.add_node("method:stmt_method", node_type="method", statement_id="stmt_method")
    graph.add_node("result:stmt_result", node_type="result", statement_id="stmt_result")
    graph.add_edge("method:stmt_method", "result:stmt_result", relation="supports")

    subgraph = build_small_subgraph(graph, max_nodes=4)

    assert subgraph.number_of_edges() == 1
    assert ("method:stmt_method", "result:stmt_result") in subgraph.edges


def test_search_linked_subgraph_preserves_incident_edges():
    graph = nx.DiGraph()
    graph.add_node("paper:paper_001", node_type="paper", paper_id="paper_001")
    graph.add_node(
        "statement:stmt_limitation",
        node_type="statement",
        statement_id="stmt_limitation",
        paper_id="paper_001",
    )
    graph.add_node(
        "limitation:stmt_limitation",
        node_type="limitation",
        statement_id="stmt_limitation",
        paper_id="paper_001",
    )
    graph.add_node(
        "result:stmt_result",
        node_type="result",
        statement_id="stmt_result",
        paper_id="paper_001",
    )
    graph.add_edge("paper:paper_001", "statement:stmt_limitation", relation="contains")
    graph.add_edge("result:stmt_result", "limitation:stmt_limitation", relation="limited_by")
    result = {
        "result_type": "statement",
        "result_id": "stmt_limitation",
        "statement_id": "stmt_limitation",
        "statement_type": "limitation",
        "paper_id": "paper_001",
    }

    subgraph = _subgraph_for_results(graph, [result], max_nodes=4)

    assert subgraph.number_of_edges() == 2
    assert ("paper:paper_001", "statement:stmt_limitation") in subgraph.edges
    assert ("result:stmt_result", "limitation:stmt_limitation") in subgraph.edges


def test_dashboard_counts_and_file_presence(tmp_path):
    db_path = tmp_path / "papers.sqlite"
    create_sample_db(db_path)
    data = load_processed_data(db_path)
    graph = nx.DiGraph()
    graph.add_node("paper:paper_001", node_type="paper")
    discovery = {"gaps": [{"gap_id": "gap_001"}], "hypotheses": [{"hypothesis_id": "hyp_001"}]}
    evaluation = {"safety_score": 1.0, "grounding_score": 1.0}

    counts = dashboard_counts(data, graph, discovery, evaluation)
    presence = file_presence([db_path, tmp_path / "missing.json"])

    assert counts["papers"] == 1
    assert counts["gaps"] == 1
    assert counts["safety_score"] == 1.0
    assert presence.to_dict("records")[0]["present"] is True
    assert presence.to_dict("records")[1]["present"] is False


def test_evaluation_status_distinguishes_caveats_from_pass():
    evaluation = {
        "safety_score": 1.0,
        "grounding_score": 0.78,
        "failed_checks": [],
        "warnings": [
            {"level": "info", "message": "Evidence currently comes from one paper or fewer."}
        ],
    }

    status = evaluation_status_summary(evaluation)
    caveats = _evaluation_caveat_items(evaluation)

    assert status["key"] == "caveats"
    assert status["headline"] == "Checks passed with caveats"
    assert status["pill_text"] == "Review caveats"
    assert status["tone"] == "warn"
    assert caveats[0] == "Grounding score is 0.78; keep outputs tied to local evidence IDs."
    assert "Evidence currently comes from one paper or fewer." in caveats


def test_evaluation_status_handles_missing_and_failed_reports():
    missing_status = evaluation_status_summary({})
    failed_status = evaluation_status_summary(
        {
            "safety_score": 0.5,
            "grounding_score": 0.9,
            "failed_checks": [{"check": "grounding"}],
            "warnings": [],
        }
    )

    assert missing_status["key"] == "missing"
    assert missing_status["headline"] == "Evaluation pending"
    assert _evaluation_caveat_items({}) == [
        "Evaluation artifacts are missing; run the local evaluation command."
    ]
    assert failed_status["key"] == "failed"
    assert failed_status["headline"] == "Safety review needed"
    assert failed_status["failed_count"] == 1


def test_evaluation_status_passes_only_without_failures_warnings_or_grounding_caveat():
    status = evaluation_status_summary(
        {
            "safety_score": 1.0,
            "grounding_score": 1.0,
            "failed_checks": [],
            "warnings": [],
        }
    )

    assert status["key"] == "passed"
    assert status["headline"] == "Checks passed"
    assert status["tone"] == "good"


def test_evidence_statement_ids_for_result_prefers_direct_and_related_ids():
    data = {
        "statements": [
            {"statement_id": "stmt_direct"},
            {"statement_id": "stmt_gap"},
            {"statement_id": "stmt_hyp"},
        ],
        "gaps": [{"gap_id": "gap_001", "source_statement_ids": ["stmt_gap"]}],
        "hypotheses": [
            {
                "hypothesis_id": "hyp_001",
                "gap_id": "gap_001",
                "evidence_statement_ids": ["stmt_hyp"],
            }
        ],
        "experiment_plans": [{"hypothesis_id": "hyp_001"}],
    }
    statement_result = {"result_type": "statement", "statement_id": "stmt_direct"}
    plan_result = {
        "result_type": "experiment_plan",
        "linked_hypothesis_id": "hyp_001",
    }

    assert _evidence_statement_ids_for_result(statement_result, data) == ["stmt_direct"]
    assert _evidence_statement_ids_for_result(plan_result, data) == ["stmt_hyp"]
    assert _available_statement_ids(["stmt_hyp", "missing"], data) == ["stmt_hyp"]


def test_statement_option_label_includes_type_paper_preview_and_id():
    label = _statement_option_label(
        {
            "statement_id": "stmt_001",
            "statement_type": "limitation",
            "paper_id": "paper_001",
            "statement_text": (
                "This evaluation uses a narrow dataset and should be reviewed carefully."
            ),
        },
        max_chars=46,
    )

    assert label.startswith("limitation | paper_001 | This evaluation uses a narrow dataset")
    assert label.endswith("(stmt_001)")


def test_load_json_file_reads_payload(tmp_path):
    json_path = tmp_path / "payload.json"
    json_path.write_text(json.dumps({"gaps": []}), encoding="utf-8")

    assert load_json_file(json_path) == {"gaps": []}


def test_render_dataframe_falls_back_for_legacy_streamlit_width(monkeypatch):
    calls = []

    def fake_dataframe(data, **kwargs):
        calls.append((data, kwargs))
        if kwargs.get("width") == "stretch":
            raise TypeError("'str' object cannot be interpreted as an integer")

    monkeypatch.setattr("ui.streamlit_app.st.dataframe", fake_dataframe)

    _render_dataframe({"rows": []})

    assert calls == [
        ({"rows": []}, {"width": "stretch"}),
        ({"rows": []}, {"use_container_width": True}),
    ]


def test_render_plotly_chart_falls_back_for_legacy_streamlit_width(monkeypatch):
    calls = []

    def fake_plotly_chart(fig, **kwargs):
        calls.append((fig, kwargs))
        if kwargs.get("width") == "stretch":
            raise TypeError("'str' object cannot be interpreted as an integer")

    monkeypatch.setattr("ui.streamlit_app.st.plotly_chart", fake_plotly_chart)

    _render_plotly_chart("figure")

    assert calls == [
        ("figure", {"width": "stretch"}),
        ("figure", {"use_container_width": True}),
    ]
