import json

import networkx as nx

from tools.graph_tools import export_graphml
from tools.storage_tools import initialize_database, save_chunk, save_paper, save_statement
from ui.streamlit_app import (
    build_small_subgraph,
    dashboard_counts,
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


def test_load_json_file_reads_payload(tmp_path):
    json_path = tmp_path / "payload.json"
    json_path.write_text(json.dumps({"gaps": []}), encoding="utf-8")

    assert load_json_file(json_path) == {"gaps": []}
