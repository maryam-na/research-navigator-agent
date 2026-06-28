import json

import pandas as pd

from ui.data_access import (
    build_ingestion_status,
    build_research_themes,
    create_research_brief,
    evidence_for_statement_ids,
    get_related_items,
    load_processed_data,
    rank_gaps,
    rank_results,
    search_gaps,
    search_hypotheses,
    search_statements,
    score_statement_quality,
)


def sample_statements() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "statement_id": "stmt_limitation",
                "paper_id": "paper_001",
                "chunk_id": "paper_001:chunk_0000",
                "statement_type": "limitation",
                "statement_text": "A limitation is that AI systems for scientific discovery are weakly evaluated.",
                "evidence_text": "A limitation is that AI systems for scientific discovery are weakly evaluated.",
            },
            {
                "statement_id": "stmt_method",
                "paper_id": "paper_001",
                "chunk_id": "paper_001:chunk_0001",
                "statement_type": "method",
                "statement_text": "We propose automated hypothesis generation from papers.",
                "evidence_text": "We propose automated hypothesis generation from papers.",
            },
        ]
    )


def test_search_finds_matching_statements():
    results = search_statements("scientific discovery limitations", sample_statements())

    assert len(results) == 1
    assert results[0]["statement_id"] == "stmt_limitation"


def test_search_filters_by_statement_type():
    results = search_statements(
        "hypothesis generation",
        sample_statements(),
        filters={"statement_type": "method"},
    )

    assert [result["statement_id"] for result in results] == ["stmt_method"]
    assert search_statements(
        "hypothesis generation",
        sample_statements(),
        filters={"statement_type": "limitation"},
    ) == []


def test_ranking_is_deterministic():
    results = [
        {"result_type": "statement", "result_id": "b", "score": 10},
        {"result_type": "gap", "result_id": "a", "score": 10},
        {"result_type": "statement", "result_id": "a", "score": 20},
    ]

    assert rank_results("query", results) == [
        {"result_type": "statement", "result_id": "a", "score": 20},
        {"result_type": "gap", "result_id": "a", "score": 10},
        {"result_type": "statement", "result_id": "b", "score": 10},
    ]


def test_empty_query_returns_no_misleading_results():
    assert search_statements("", sample_statements()) == []
    assert search_gaps("", [{"gap_id": "gap_001"}]) == []
    assert search_hypotheses("", [{"hypothesis_id": "hyp_001"}]) == []


def test_related_gaps_and_hypotheses_are_found_by_evidence_ids():
    result = {"result_type": "statement", "result_id": "stmt_limitation", "statement_id": "stmt_limitation"}
    gaps = [{"gap_id": "gap_001", "source_statement_ids": ["stmt_limitation"]}]
    hypotheses = [
        {
            "hypothesis_id": "hyp_001",
            "gap_id": "gap_001",
            "evidence_statement_ids": ["stmt_limitation"],
        }
    ]
    plans = [{"hypothesis_id": "hyp_001", "plan": {"objective": "Test it."}}]

    related = get_related_items(result, gaps, hypotheses, plans)

    assert related["gaps"] == gaps
    assert related["hypotheses"] == hypotheses
    assert related["experiment_plans"] == plans


def test_load_processed_data_handles_missing_files(tmp_path):
    data = load_processed_data(
        tmp_path / "missing.sqlite",
        gaps_path=tmp_path / "missing.json",
        evaluation_path=tmp_path / "missing_eval.json",
        graph_path=tmp_path / "missing.graphml",
    )

    assert data["papers"].empty
    assert data["statements"].empty
    assert data["gaps"] == []
    assert data["hypotheses"] == []
    assert data["evaluation"] == {}
    assert data["graph"].number_of_nodes() == 0


def test_load_processed_data_reads_discovery_json(tmp_path):
    gaps_path = tmp_path / "gaps.json"
    gaps_path.write_text(
        json.dumps(
            {
                "gaps": [{"gap_id": "gap_001"}],
                "hypotheses": [{"hypothesis_id": "hyp_001"}],
                "experiment_plans": [{"hypothesis_id": "hyp_001", "plan": {}}],
            }
        ),
        encoding="utf-8",
    )

    data = load_processed_data(tmp_path / "missing.sqlite", gaps_path=gaps_path)

    assert data["gaps"] == [{"gap_id": "gap_001"}]
    assert data["hypotheses"] == [{"hypothesis_id": "hyp_001"}]


def test_evidence_inspector_returns_compact_grounding_rows():
    evidence = evidence_for_statement_ids(["stmt_limitation"], sample_statements(), max_chars=40)

    assert evidence == [
        {
            "statement_id": "stmt_limitation",
            "paper_id": "paper_001",
            "statement_type": "limitation",
            "statement_text": "A limitation is that AI systems for s...",
            "evidence_text": "A limitation is that AI systems for s...",
        }
    ]


def test_statement_quality_scores_are_deterministic():
    statement = sample_statements().iloc[0].to_dict()

    quality = score_statement_quality(statement)

    assert quality["statement_id"] == "stmt_limitation"
    assert quality["grounding_confidence"] == 1.0
    assert quality["overall_quality"] > 0.5


def test_rank_gaps_prefers_more_evidence():
    gaps = [
        {"gap_id": "gap_low", "gap_type": "limitation", "source_statement_ids": ["stmt_limitation"]},
        {
            "gap_id": "gap_high",
            "gap_type": "result_with_limitation",
            "source_statement_ids": ["stmt_limitation", "stmt_method"],
        },
    ]

    ranked = rank_gaps(gaps, sample_statements())

    assert [gap["gap_id"] for gap in ranked] == ["gap_high", "gap_low"]
    assert ranked[0]["evidence_count"] == 2


def test_research_themes_are_deterministic():
    themes = build_research_themes(sample_statements(), max_themes=2)

    assert len(themes) == 2
    assert themes == build_research_themes(sample_statements(), max_themes=2)
    assert themes[0]["statement_count"] == 1


def test_ingestion_status_summarizes_paper_progress():
    data = {
        "papers": pd.DataFrame([{"paper_id": "paper_001", "title": "Synthetic Paper"}]),
        "chunks": pd.DataFrame([{"paper_id": "paper_001", "chunk_id": "chunk_1"}]),
        "statements": sample_statements(),
        "gaps": [{"source_statement_ids": ["stmt_limitation"]}],
        "hypotheses": [{"evidence_statement_ids": ["stmt_limitation"]}],
    }

    status = build_ingestion_status(data).to_dict("records")[0]

    assert status["status"] == "experiment-ready"
    assert status["chunk_count"] == 1
    assert status["statement_count"] == 2


def test_research_brief_contains_ranked_sections():
    data = {
        "statements": sample_statements(),
        "gaps": [
            {
                "gap_id": "gap_001",
                "gap_type": "limitation",
                "gap_text": "Evaluation remains limited.",
                "source_statement_ids": ["stmt_limitation"],
            }
        ],
        "hypotheses": [
            {
                "hypothesis_id": "hyp_001",
                "gap_id": "gap_001",
                "hypothesis_text": "A controlled evaluation may clarify the limitation.",
                "confidence_level": "low",
                "safety_label": "speculative_research_hypothesis",
            }
        ],
        "graph": None,
    }

    brief = create_research_brief(data)

    assert "# ResearchNavigator Local Brief" in brief
    assert "## Ranked Research Gaps" in brief
    assert "gap_001" in brief
