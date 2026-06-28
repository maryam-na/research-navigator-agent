from scripts.project_stats import calculate_project_stats
from tools.storage_tools import initialize_database, save_chunk, save_paper, save_statement


def test_calculate_project_stats_reports_counts_and_context_estimate(tmp_path):
    db_path = tmp_path / "research.db"
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

    stats = calculate_project_stats(str(db_path))

    assert stats["papers"] == 1
    assert stats["chunks"] == 1
    assert stats["statements"] == 1
    assert stats["average_statement_length"] > 0
    assert stats["graph_nodes"] == 3
    assert stats["graph_edges"] == 1
    assert stats["estimated_top_20_statement_context_tokens"] > 0
