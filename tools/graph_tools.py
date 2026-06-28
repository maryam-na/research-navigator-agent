"""Deterministic NetworkX graph construction for extracted research statements."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import networkx as nx


SEMANTIC_TYPES = {
    "method",
    "result",
    "limitation",
    "future_work",
    "dataset",
    "background",
    "unknown",
}

RELATION_TARGET_CAPS = {
    "supports": 2,
    "limited_by": 2,
    "motivates": 2,
    "used_by": 2,
}


def _require_statement_field(statement: dict, field: str) -> str:
    value = statement.get(field)
    if value is None or str(value).strip() == "":
        raise ValueError(f"statement is missing required field: {field}")
    return str(value).strip()


def _semantic_node_id(statement: dict) -> str:
    statement_type = _require_statement_field(statement, "statement_type")
    if statement_type not in SEMANTIC_TYPES:
        statement_type = "unknown"
    return f"{statement_type}:{_require_statement_field(statement, 'statement_id')}"


def statement_to_node_id(statement: dict) -> str:
    """Return the deterministic provenance node id for a statement."""

    return f"statement:{_require_statement_field(statement, 'statement_id')}"


def add_statement_nodes(graph: nx.DiGraph, statements: list[dict]) -> None:
    """Add paper, statement, and semantic statement-type nodes to the graph."""

    for statement in sorted(statements, key=_statement_sort_key):
        paper_id = _require_statement_field(statement, "paper_id")
        chunk_id = _require_statement_field(statement, "chunk_id")
        statement_id = _require_statement_field(statement, "statement_id")
        statement_type = statement.get("statement_type", "unknown")
        if statement_type not in SEMANTIC_TYPES:
            statement_type = "unknown"

        paper_node_id = f"paper:{paper_id}"
        statement_node_id = statement_to_node_id(statement)
        semantic_node_id = _semantic_node_id(statement)
        sentence_index = int(statement.get("sentence_index", 0))

        graph.add_node(paper_node_id, node_type="paper", paper_id=paper_id)
        graph.add_node(
            statement_node_id,
            node_type="statement",
            statement_id=statement_id,
            paper_id=paper_id,
            chunk_id=chunk_id,
            statement_type=statement_type,
            statement_text=str(statement.get("statement_text", "")),
            evidence_text=str(statement.get("evidence_text", "")),
            confidence_rule=str(statement.get("confidence_rule", "")),
            sentence_index=sentence_index,
        )
        graph.add_node(
            semantic_node_id,
            node_type=statement_type,
            statement_id=statement_id,
            paper_id=paper_id,
            chunk_id=chunk_id,
            statement_text=str(statement.get("statement_text", "")),
            evidence_text=str(statement.get("evidence_text", "")),
            confidence_rule=str(statement.get("confidence_rule", "")),
            sentence_index=sentence_index,
        )
        graph.add_edge(paper_node_id, statement_node_id, relation="contains")


def add_semantic_edges(graph: nx.DiGraph) -> None:
    """Add deterministic semantic edges between statement-type nodes in the same paper."""

    semantic_nodes_by_type: dict[str, list[tuple[str, dict]]] = {
        statement_type: [] for statement_type in SEMANTIC_TYPES
    }
    for node_id, attrs in graph.nodes(data=True):
        node_type = attrs.get("node_type")
        if node_type in SEMANTIC_TYPES:
            semantic_nodes_by_type[node_type].append((node_id, attrs))

    for nodes in semantic_nodes_by_type.values():
        nodes.sort(key=lambda item: _node_sort_key(item[0], item[1]))

    _add_nearest_edges_for_same_paper(
        graph,
        semantic_nodes_by_type["method"],
        semantic_nodes_by_type["result"],
        "supports",
    )
    _add_nearest_edges_for_same_paper(
        graph,
        semantic_nodes_by_type["result"],
        semantic_nodes_by_type["limitation"],
        "limited_by",
    )
    _add_nearest_edges_for_same_paper(
        graph,
        semantic_nodes_by_type["limitation"],
        semantic_nodes_by_type["future_work"],
        "motivates",
    )
    _add_nearest_edges_for_same_paper(
        graph,
        semantic_nodes_by_type["dataset"],
        semantic_nodes_by_type["method"],
        "used_by",
    )


def build_research_graph(statements: list[dict]) -> nx.DiGraph:
    """Build a deterministic local research graph from extracted statements."""

    graph = nx.DiGraph()
    add_statement_nodes(graph, statements)
    add_semantic_edges(graph)
    return graph


def export_graphml(graph: nx.DiGraph, path: str) -> None:
    """Export the graph to a local GraphML file."""

    graph_path = _resolve_local_output_path(path)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(_sanitize_graph_for_graphml(graph), graph_path)


def graph_summary(graph: nx.DiGraph) -> dict:
    """Return deterministic counts for graph nodes, edges, node types, and relations."""

    node_type_counts = Counter(str(attrs.get("node_type", "unknown")) for _, attrs in graph.nodes(data=True))
    relation_counts = Counter(str(attrs.get("relation", "unknown")) for _, _, attrs in graph.edges(data=True))
    return {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "node_types": dict(sorted(node_type_counts.items())),
        "relation_types": dict(sorted(relation_counts.items())),
    }


def _statement_sort_key(statement: dict) -> tuple[str, str, int, str]:
    return (
        str(statement.get("paper_id", "")),
        str(statement.get("chunk_id", "")),
        int(statement.get("sentence_index", 0)),
        str(statement.get("statement_id", "")),
    )


def _node_sort_key(node_id: str, attrs: dict) -> tuple[str, str, int, str]:
    return (
        str(attrs.get("paper_id", "")),
        str(attrs.get("chunk_id", "")),
        int(attrs.get("sentence_index", 0)),
        node_id,
    )


def _add_nearest_edges_for_same_paper(
    graph: nx.DiGraph,
    source_nodes: list[tuple[str, dict]],
    target_nodes: list[tuple[str, dict]],
    relation: str,
) -> None:
    max_targets = RELATION_TARGET_CAPS[relation]
    for source_id, source_attrs in source_nodes:
        candidates = [
            (target_id, target_attrs)
            for target_id, target_attrs in target_nodes
            if source_attrs.get("paper_id") == target_attrs.get("paper_id")
        ]
        ranked_candidates = sorted(
            candidates,
            key=lambda item: (
                _position_distance(source_attrs, item[1]),
                _is_backward(source_attrs, item[1]),
                _node_sort_key(item[0], item[1]),
            ),
        )
        for target_id, _target_attrs in ranked_candidates[:max_targets]:
            graph.add_edge(source_id, target_id, relation=relation)


def _position_distance(source_attrs: dict, target_attrs: dict) -> tuple[int, int]:
    source_chunk = _chunk_index(source_attrs)
    target_chunk = _chunk_index(target_attrs)
    source_sentence = int(source_attrs.get("sentence_index", 0))
    target_sentence = int(target_attrs.get("sentence_index", 0))
    return (abs(target_chunk - source_chunk), abs(target_sentence - source_sentence))


def _is_backward(source_attrs: dict, target_attrs: dict) -> int:
    source_pos = (_chunk_index(source_attrs), int(source_attrs.get("sentence_index", 0)))
    target_pos = (_chunk_index(target_attrs), int(target_attrs.get("sentence_index", 0)))
    return int(target_pos < source_pos)


def _chunk_index(attrs: dict) -> int:
    chunk_id = str(attrs.get("chunk_id", ""))
    match = re.search(r"chunk_(\d+)", chunk_id)
    if not match:
        return 0
    return int(match.group(1))


def _resolve_local_output_path(path_value: str) -> Path:
    if not path_value or not path_value.strip():
        raise ValueError("path must be a non-empty local file path.")

    parsed = urlparse(path_value)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError("Only local GraphML output paths are supported.")

    path = Path(parsed.path if parsed.scheme == "file" else path_value).expanduser()
    if path.exists() and path.is_dir():
        raise ValueError(f"GraphML path points to a directory: {path}")
    return path


def _sanitize_graph_for_graphml(graph: nx.DiGraph) -> nx.DiGraph:
    sanitized = nx.DiGraph()
    for node_id, attrs in graph.nodes(data=True):
        sanitized.add_node(_xml_safe_text(str(node_id)), **_xml_safe_attrs(attrs))
    for source, target, attrs in graph.edges(data=True):
        sanitized.add_edge(
            _xml_safe_text(str(source)),
            _xml_safe_text(str(target)),
            **_xml_safe_attrs(attrs),
        )
    return sanitized


def _xml_safe_attrs(attrs: dict) -> dict:
    return {key: _xml_safe_value(value) for key, value in attrs.items()}


def _xml_safe_value(value):
    if isinstance(value, str):
        return _xml_safe_text(value)
    return value


def _xml_safe_text(text: str) -> str:
    return "".join(
        char
        for char in text
        if char in {"\t", "\n", "\r"} or ord(char) >= 0x20
    )
