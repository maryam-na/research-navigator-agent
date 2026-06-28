"""Build and export a local research knowledge graph from SQLite statements."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import networkx as nx

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.graph_tools import build_research_graph, export_graphml, graph_summary
from tools.storage_tools import get_statements


def build_graph_from_database(
    db_path: str,
    graph_path: str,
    max_nodes: int = 3000,
    allow_truncate: bool = False,
) -> dict:
    if max_nodes <= 0:
        raise ValueError("max_nodes must be greater than 0.")

    statements = get_statements(db_path)
    graph = build_research_graph(statements)
    summary = graph_summary(graph)
    if summary["nodes"] > max_nodes:
        print(
            "Warning: graph has "
            f"{summary['nodes']} nodes, which exceeds --max-nodes={max_nodes}. "
            "Use filtered statements during ingestion, for example "
            "`--extract-statements --filter-statements`, to reduce graph size.",
            file=sys.stderr,
        )
        if not allow_truncate:
            print(
                "Graph was not exported. Re-run with --allow-truncate to export a "
                "deterministic truncated graph.",
                file=sys.stderr,
            )
            summary["exported"] = False
            summary["truncated"] = False
            return summary
        graph = _truncate_graph(graph, max_nodes)
        summary = graph_summary(graph)
        summary["truncated"] = True

    export_graphml(graph, graph_path)
    summary["exported"] = True
    summary.setdefault("truncated", False)
    return summary


def _truncate_graph(graph: nx.DiGraph, max_nodes: int) -> nx.DiGraph:
    selected_nodes = sorted(str(node_id) for node_id in graph.nodes())[:max_nodes]
    return graph.subgraph(selected_nodes).copy()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a local GraphML research graph from extracted statements.",
    )
    parser.add_argument(
        "--db-path",
        default="data/processed/papers.sqlite",
        help="SQLite database path containing extracted statements.",
    )
    parser.add_argument(
        "--graph-path",
        default="data/processed/research_graph.graphml",
        help="Output GraphML path.",
    )
    parser.add_argument(
        "--max-nodes",
        type=int,
        default=3000,
        help="Warn and skip export if the graph exceeds this many nodes.",
    )
    parser.add_argument(
        "--allow-truncate",
        action="store_true",
        help="Export the graph even when it exceeds --max-nodes.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        summary = build_graph_from_database(
            args.db_path,
            args.graph_path,
            max_nodes=args.max_nodes,
            allow_truncate=args.allow_truncate,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Graph nodes: {summary['nodes']}")
    print(f"Graph edges: {summary['edges']}")
    print(f"Node types: {summary['node_types']}")
    print(f"Relation types: {summary['relation_types']}")
    print(f"Exported: {summary['exported']}")
    print(f"Truncated: {summary['truncated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
