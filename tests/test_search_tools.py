import json

import pandas as pd

from ui.data_access import (
    build_evidence_chain,
    build_ingestion_status,
    build_research_themes,
    create_research_brief,
    evidence_for_statement_ids,
    get_related_items,
    load_processed_data,
    prepare_hypothesis_triage,
    rank_gaps,
    rank_results,
    score_statement_quality,
    search_gaps,
    search_hypotheses,
    search_statements,
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


def test_build_evidence_chain_summarizes_linked_outputs_with_clipped_snippets():
    long_text = "This limitation describes a narrow evaluation setting with sparse noisy data. " * 4
    data = {
        "papers": pd.DataFrame([{"paper_id": "paper_001", "title": "Synthetic Evidence Paper"}]),
        "statements": pd.DataFrame(
            [
                {
                    "statement_id": "stmt_long",
                    "paper_id": "paper_001",
                    "chunk_id": "paper_001:chunk_0000",
                    "statement_type": "limitation",
                    "statement_text": long_text,
                    "evidence_text": long_text,
                }
            ]
        ),
        "gaps": [
            {
                "gap_id": "gap_001",
                "gap_type": "limitation",
                "gap_text": "A possible research gap is suggested by a reported limitation.",
                "source_statement_ids": ["stmt_long"],
                "paper_ids": ["paper_001"],
            }
        ],
        "hypotheses": [
            {
                "hypothesis_id": "hyp_001",
                "gap_id": "gap_001",
                "hypothesis_text": "A testable hypothesis could be evaluated locally.",
                "confidence_level": "low",
                "safety_label": "speculative_research_hypothesis",
                "evidence_statement_ids": ["stmt_long"],
            }
        ],
        "experiment_plans": [
            {
                "hypothesis_id": "hyp_001",
                "plan": {
                    "objective": "Test the candidate hypothesis.",
                    "method": "Compare against a baseline.",
                    "metrics": ["robustness", "coverage"],
                },
            }
        ],
    }
    result = {"result_type": "statement", "result_id": "stmt_long", "statement_id": "stmt_long"}

    chain = build_evidence_chain(result, data, max_chars=80)

    assert chain["evidence"][0]["status"] == "available"
    assert chain["evidence"][0]["paper_title"] == "Synthetic Evidence Paper"
    assert chain["evidence"][0]["statement_text"].endswith("...")
    assert chain["gaps"][0]["gap_id"] == "gap_001"
    assert chain["hypotheses"][0]["safety_label"] == "speculative_research_hypothesis"
    assert chain["experiment_plans"][0]["metrics"] == "robustness, coverage"


def test_build_evidence_chain_labels_missing_evidence_ids():
    data = {
        "papers": pd.DataFrame(),
        "statements": pd.DataFrame(),
        "gaps": [
            {
                "gap_id": "gap_missing",
                "gap_type": "limitation",
                "gap_text": "A possible gap with missing local evidence.",
                "source_statement_ids": ["stmt_missing"],
            }
        ],
        "hypotheses": [],
        "experiment_plans": [],
    }
    result = {"result_type": "gap", "result_id": "gap_missing", "linked_gap_id": "gap_missing"}

    chain = build_evidence_chain(result, data)

    assert chain["missing_evidence_ids"] == ["stmt_missing"]
    assert chain["evidence"][0] == {
        "statement_id": "stmt_missing",
        "status": "missing",
        "paper_id": "",
        "paper_title": "",
        "statement_type": "",
        "statement_text": "",
        "evidence_text": "",
    }


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


def test_rank_gaps_adds_triage_metadata_and_missing_evidence_status():
    gaps = [
        {
            "gap_id": "gap_missing",
            "gap_text": "A possible research gap is suggested by: Missing evidence.",
            "gap_type": "limitation",
            "source_statement_ids": [],
        },
        {
            "gap_id": "gap_supported",
            "gap_text": "A possible research gap is suggested by a reported limitation: Evaluation remains narrow.",
            "gap_type": "result_with_limitation",
            "source_statement_ids": ["stmt_limitation"],
        },
    ]

    ranked = rank_gaps(gaps, sample_statements())
    supported = ranked[0]
    missing = ranked[1]

    assert supported["gap_id"] == "gap_supported"
    assert supported["display_label"] == "Evaluation remains narrow."
    assert supported["evidence_status"] == "evidence-linked"
    assert supported["rank_score_parts"]["evidence"] == 3
    assert "evidence +3" in supported["rank_score_explanation"]
    assert missing["evidence_status"] == "missing evidence"
    assert missing["available_evidence_count"] == 0


def test_prepare_hypothesis_triage_links_gap_plan_and_safety_context():
    gaps = [
        {
            "gap_id": "gap_supported",
            "gap_text": "A possible research gap is suggested by: Evaluation remains narrow.",
            "gap_type": "result_with_limitation",
            "source_statement_ids": ["stmt_limitation", "stmt_method"],
        }
    ]
    hypotheses = [
        {
            "hypothesis_id": "hyp_missing",
            "gap_id": "gap_supported",
            "hypothesis_text": "A testable hypothesis could be that unsupported evidence should be reviewed.",
            "confidence_level": "low",
            "safety_label": "speculative_research_hypothesis",
            "evidence_statement_ids": [],
        },
        {
            "hypothesis_id": "hyp_supported",
            "gap_id": "gap_supported",
            "hypothesis_text": "A testable hypothesis could be that controlled evaluation clarifies the limitation.",
            "confidence_level": "medium",
            "safety_label": "speculative_research_hypothesis",
            "evidence_statement_ids": ["stmt_limitation", "stmt_method"],
        },
    ]
    plans = [{"hypothesis_id": "hyp_supported", "plan": {"objective": "Test it."}}]

    triaged = prepare_hypothesis_triage(hypotheses, gaps, sample_statements(), plans)

    supported = triaged[0]
    missing = triaged[1]
    assert supported["hypothesis_id"] == "hyp_supported"
    assert supported["display_label"] == "Controlled evaluation clarifies the limitation."
    assert supported["linked_gap_type"] == "result_with_limitation"
    assert supported["experiment_plan_available"] is True
    assert supported["evidence_status"] == "evidence-linked"
    assert "speculative safety label" in supported["triage_score_explanation"]
    assert missing["evidence_status"] == "missing evidence"


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
                "evidence_statement_ids": ["stmt_limitation"],
            }
        ],
        "evaluation": {
            "overall_score": 0.8,
            "grounding_score": 0.75,
            "safety_score": 1.0,
            "warnings": [
                {"level": "warning", "message": "Evidence currently comes from one paper."}
            ],
            "failed_checks": [],
        },
        "graph": None,
    }

    brief = create_research_brief(data)

    assert "# ResearchNavigator Local Brief" in brief
    assert "## Evaluation Caveats" in brief
    assert "## Ranked Research Gaps" in brief
    assert "## Candidate Hypotheses (Speculative)" in brief
    assert "gap_001" in brief
    assert "hyp_001" in brief
    assert "Evidence currently comes from one paper." in brief
    assert "Grounding is below 1.0" in brief
    assert "Evidence IDs: stmt_limitation" in brief
    assert "Paper IDs: paper_001" in brief
    assert "stmt_limitation (paper_001, limitation)" in brief
    assert "speculative_research_hypothesis" in brief
    assert "not as a proven claim" in brief


def test_research_brief_marks_missing_evaluation_and_evidence():
    data = {
        "statements": sample_statements(),
        "gaps": [
            {
                "gap_id": "gap_missing",
                "gap_type": "limitation",
                "gap_text": "A gap with stale evidence should still be labeled.",
                "source_statement_ids": ["stmt_missing"],
            }
        ],
        "hypotheses": [
            {
                "hypothesis_id": "hyp_missing",
                "gap_id": "gap_missing",
                "hypothesis_text": "A speculative follow-up may be possible.",
                "confidence_level": "low",
                "safety_label": "speculative_research_hypothesis",
            }
        ],
        "graph": None,
    }

    brief = create_research_brief(data)

    assert "Evaluation report is missing" in brief
    assert "Evidence IDs: stmt_missing" in brief
    assert "Source snippets: not available in the current statement table." in brief
    assert "Linked gap evidence IDs: stmt_missing" in brief
