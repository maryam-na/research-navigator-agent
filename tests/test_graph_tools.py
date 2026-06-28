import networkx as nx

from tools.graph_tools import (
    add_semantic_edges,
    add_statement_nodes,
    build_research_graph,
    export_graphml,
    graph_summary,
    statement_to_node_id,
)


def sample_statements() -> list[dict]:
    return [
        {
            "statement_id": "stmt_dataset",
            "paper_id": "paper_001",
            "chunk_id": "paper_001:chunk_0000",
            "statement_type": "dataset",
            "statement_text": "The benchmark dataset contains 1,200 examples.",
            "evidence_text": "The benchmark dataset contains 1,200 examples.",
            "confidence_rule": "rule:dataset",
            "sentence_index": 0,
        },
        {
            "statement_id": "stmt_method",
            "paper_id": "paper_001",
            "chunk_id": "paper_001:chunk_0000",
            "statement_type": "method",
            "statement_text": "We propose a local graph approach.",
            "evidence_text": "We propose a local graph approach.",
            "confidence_rule": "rule:we propose",
            "sentence_index": 1,
        },
        {
            "statement_id": "stmt_result",
            "paper_id": "paper_001",
            "chunk_id": "paper_001:chunk_0001",
            "statement_type": "result",
            "statement_text": "Results show it improves F1.",
            "evidence_text": "Results show it improves F1.",
            "confidence_rule": "rule:results show",
            "sentence_index": 0,
        },
        {
            "statement_id": "stmt_limitation",
            "paper_id": "paper_001",
            "chunk_id": "paper_001:chunk_0001",
            "statement_type": "limitation",
            "statement_text": "A limitation is synthetic data.",
            "evidence_text": "A limitation is synthetic data.",
            "confidence_rule": "rule:limitation",
            "sentence_index": 1,
        },
        {
            "statement_id": "stmt_future",
            "paper_id": "paper_001",
            "chunk_id": "paper_001:chunk_0002",
            "statement_type": "future_work",
            "statement_text": "Future work should investigate field data.",
            "evidence_text": "Future work should investigate field data.",
            "confidence_rule": "rule:future work",
            "sentence_index": 0,
        },
        {
            "statement_id": "stmt_background",
            "paper_id": "paper_001",
            "chunk_id": "paper_001:chunk_0002",
            "statement_type": "background",
            "statement_text": "Prior work studies graph cleaning.",
            "evidence_text": "Prior work studies graph cleaning.",
            "confidence_rule": "rule:prior work",
            "sentence_index": 1,
        },
        {
            "statement_id": "stmt_unknown",
            "paper_id": "paper_002",
            "chunk_id": "paper_002:chunk_0000",
            "statement_type": "unknown",
            "statement_text": "The paper has three sections.",
            "evidence_text": "The paper has three sections.",
            "confidence_rule": "rule:no_rule_matched",
            "sentence_index": 0,
        },
    ]


def test_statement_to_node_id_is_deterministic():
    statement = sample_statements()[0]

    assert statement_to_node_id(statement) == "statement:stmt_dataset"


def test_graph_builds_from_sample_statements():
    graph = build_research_graph(sample_statements())

    assert isinstance(graph, nx.DiGraph)
    assert graph.has_node("paper:paper_001")
    assert graph.has_node("statement:stmt_method")
    assert graph.has_node("method:stmt_method")
    assert graph.nodes["paper:paper_001"]["node_type"] == "paper"
    assert graph.nodes["statement:stmt_method"]["node_type"] == "statement"
    assert graph.nodes["method:stmt_method"]["node_type"] == "method"


def test_expected_node_types_exist():
    graph = build_research_graph(sample_statements())
    node_types = {attrs["node_type"] for _, attrs in graph.nodes(data=True)}

    assert {
        "paper",
        "statement",
        "method",
        "result",
        "limitation",
        "future_work",
        "dataset",
        "background",
        "unknown",
    }.issubset(node_types)


def test_expected_edge_relations_exist():
    graph = build_research_graph(sample_statements())
    edges = {(source, target, attrs["relation"]) for source, target, attrs in graph.edges(data=True)}

    assert ("paper:paper_001", "statement:stmt_method", "contains") in edges
    assert ("method:stmt_method", "result:stmt_result", "supports") in edges
    assert ("result:stmt_result", "limitation:stmt_limitation", "limited_by") in edges
    assert ("limitation:stmt_limitation", "future_work:stmt_future", "motivates") in edges
    assert ("dataset:stmt_dataset", "method:stmt_method", "used_by") in edges


def test_semantic_edges_only_connect_same_paper():
    graph = build_research_graph(
        sample_statements()
        + [
            {
                "statement_id": "stmt_other_result",
                "paper_id": "paper_002",
                "chunk_id": "paper_002:chunk_0000",
                "statement_type": "result",
                "statement_text": "Results show a separate finding.",
                "evidence_text": "Results show a separate finding.",
                "confidence_rule": "rule:results show",
                "sentence_index": 1,
            }
        ]
    )

    assert not graph.has_edge("method:stmt_method", "result:stmt_other_result")


def test_semantic_edges_are_capped_per_source():
    statements = [
        {
            "statement_id": "stmt_method",
            "paper_id": "paper_001",
            "chunk_id": "paper_001:chunk_0000",
            "statement_type": "method",
            "statement_text": "We propose a local graph approach.",
            "evidence_text": "We propose a local graph approach.",
            "confidence_rule": "rule:we propose",
            "sentence_index": 0,
        }
    ]
    for index in range(5):
        statements.append(
            {
                "statement_id": f"stmt_result_{index}",
                "paper_id": "paper_001",
                "chunk_id": f"paper_001:chunk_{index + 1:04d}",
                "statement_type": "result",
                "statement_text": f"Results show finding {index}.",
                "evidence_text": f"Results show finding {index}.",
                "confidence_rule": "rule:results show",
                "sentence_index": 0,
            }
        )

    graph = build_research_graph(statements)
    support_edges = [
        (source, target)
        for source, target, attrs in graph.edges(data=True)
        if source == "method:stmt_method" and attrs["relation"] == "supports"
    ]

    assert len(support_edges) == 2


def test_add_statement_nodes_and_semantic_edges_can_be_called_separately():
    graph = nx.DiGraph()

    add_statement_nodes(graph, sample_statements())
    assert graph.has_edge("paper:paper_001", "statement:stmt_result")
    assert not graph.has_edge("method:stmt_method", "result:stmt_result")

    add_semantic_edges(graph)
    assert graph.has_edge("method:stmt_method", "result:stmt_result")


def test_graph_summary_is_deterministic():
    graph = build_research_graph(sample_statements())

    assert graph_summary(graph) == {
        "nodes": 16,
        "edges": 11,
        "node_types": {
            "background": 1,
            "dataset": 1,
            "future_work": 1,
            "limitation": 1,
            "method": 1,
            "paper": 2,
            "result": 1,
            "statement": 7,
            "unknown": 1,
        },
        "relation_types": {
            "contains": 7,
            "limited_by": 1,
            "motivates": 1,
            "supports": 1,
            "used_by": 1,
        },
    }


def test_graph_export_creates_file(tmp_path):
    graph = build_research_graph(sample_statements())
    graph_path = tmp_path / "nested" / "research_graph.graphml"

    export_graphml(graph, str(graph_path))

    assert graph_path.exists()
    assert graph_path.read_text(encoding="utf-8").startswith("<?xml")


def test_graph_export_sanitizes_xml_invalid_text(tmp_path):
    graph = nx.DiGraph()
    graph.add_node("statement:bad", node_type="statement", statement_text="bad\x08text")
    graph_path = tmp_path / "safe.graphml"

    export_graphml(graph, str(graph_path))

    assert graph_path.exists()
    assert "\x08" not in graph_path.read_text(encoding="utf-8")
