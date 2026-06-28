"""Print lightweight local project statistics for graph and context sizing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.graph_tools import build_research_graph, graph_summary
from tools.storage_tools import get_chunks, get_papers, get_statements


def calculate_project_stats(db_path: str, top_statement_count: int = 20) -> dict:
    if top_statement_count <= 0:
        raise ValueError("top_statement_count must be greater than 0.")

    papers = get_papers(db_path)
    chunks = get_chunks(db_path)
    statements = get_statements(db_path)
    graph = build_research_graph(statements)
    summary = graph_summary(graph)

    statement_lengths = [len(str(statement.get("statement_text", ""))) for statement in statements]
    average_statement_length = (
        round(sum(statement_lengths) / len(statement_lengths), 2) if statement_lengths else 0.0
    )
    top_statements = sorted(
        statements,
        key=lambda statement: (
            str(statement.get("paper_id", "")),
            str(statement.get("chunk_id", "")),
            int(statement.get("sentence_index", 0)),
            str(statement.get("statement_id", "")),
        ),
    )[:top_statement_count]
    context_chars = sum(len(str(statement.get("statement_text", ""))) for statement in top_statements)
    estimated_tokens = max(1, round(context_chars / 4)) if context_chars else 0

    return {
        "papers": len(papers),
        "chunks": len(chunks),
        "statements": len(statements),
        "average_statement_length": average_statement_length,
        "graph_nodes": summary["nodes"],
        "graph_edges": summary["edges"],
        "estimated_top_20_statement_context_tokens": estimated_tokens,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print local ResearchNavigator corpus and graph statistics.",
    )
    parser.add_argument(
        "--db-path",
        default="data/processed/papers.sqlite",
        help="SQLite database path containing papers, chunks, and statements.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        stats = calculate_project_stats(args.db_path)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Papers: {stats['papers']}")
    print(f"Chunks: {stats['chunks']}")
    print(f"Statements: {stats['statements']}")
    print(f"Average statement length: {stats['average_statement_length']}")
    print(f"Graph nodes: {stats['graph_nodes']}")
    print(f"Graph edges: {stats['graph_edges']}")
    print(
        "Estimated LLM context tokens for top 20 statements: "
        f"{stats['estimated_top_20_statement_context_tokens']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

