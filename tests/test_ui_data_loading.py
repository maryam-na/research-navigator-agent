import json
import os

import networkx as nx

from tools.graph_tools import export_graphml
from tools.storage_tools import initialize_database, save_chunk, save_paper, save_statement
from ui.streamlit_app import (
    _artifact_readiness_summary,
    _available_statement_ids,
    _evaluation_caveat_items,
    _evidence_statement_ids_for_result,
    _filter_gap_triage,
    _filter_hypothesis_triage,
    _global_safety_threshold_message,
    _limit_search_results,
    _load_ui_settings,
    _render_dataframe,
    _render_plotly_chart,
    _result_card_preview,
    _result_card_title,
    _result_metadata_tags,
    _sort_gap_triage,
    _sort_hypothesis_triage,
    _statement_option_label,
    _subgraph_for_results,
    build_artifact_readiness,
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


def write_artifact(path, modified_time):
    path.write_text("artifact", encoding="utf-8")
    os.utime(path, (modified_time, modified_time))


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


def test_artifact_readiness_reports_all_ready_when_outputs_are_current(tmp_path):
    db_path = tmp_path / "papers.sqlite"
    graph_path = tmp_path / "graph.graphml"
    discovery_path = tmp_path / "gaps.json"
    evaluation_path = tmp_path / "evaluation.json"
    brief_path = tmp_path / "brief.md"
    write_artifact(db_path, 100)
    write_artifact(graph_path, 110)
    write_artifact(discovery_path, 120)
    write_artifact(evaluation_path, 130)
    write_artifact(brief_path, 140)

    readiness = build_artifact_readiness(
        [
            {
                "key": "database",
                "label": "Database",
                "path": db_path,
                "recovery_step": "ingest",
            },
            {
                "key": "graph",
                "label": "Graph",
                "path": graph_path,
                "depends_on": [db_path],
                "recovery_step": "build graph",
            },
            {
                "key": "discoveries",
                "label": "Discoveries",
                "path": discovery_path,
                "depends_on": [db_path],
                "recovery_step": "discover",
            },
            {
                "key": "evaluation",
                "label": "Evaluation",
                "path": evaluation_path,
                "depends_on": [db_path, discovery_path],
                "recovery_step": "evaluate",
            },
            {
                "key": "brief",
                "label": "Brief",
                "path": brief_path,
                "depends_on": [discovery_path, evaluation_path],
                "recovery_step": "brief",
            },
        ]
    )

    assert readiness["status"] == "ready"
    assert readiness["counts"] == {"ready": 5, "missing": 0, "stale": 0, "total": 5}
    assert readiness["problem_artifacts"] == []


def test_artifact_readiness_flags_missing_and_stale_outputs(tmp_path):
    db_path = tmp_path / "papers.sqlite"
    graph_path = tmp_path / "graph.graphml"
    discovery_path = tmp_path / "gaps.json"
    evaluation_path = tmp_path / "evaluation.json"
    brief_path = tmp_path / "brief.md"
    write_artifact(db_path, 200)
    write_artifact(graph_path, 100)
    write_artifact(evaluation_path, 250)
    write_artifact(brief_path, 260)

    readiness = build_artifact_readiness(
        [
            {
                "key": "database",
                "label": "Database",
                "path": db_path,
                "recovery_step": "ingest",
            },
            {
                "key": "graph",
                "label": "Graph",
                "path": graph_path,
                "depends_on": [db_path],
                "recovery_step": "build graph",
            },
            {
                "key": "discoveries",
                "label": "Discoveries",
                "path": discovery_path,
                "depends_on": [db_path],
                "recovery_step": "discover",
            },
            {
                "key": "evaluation",
                "label": "Evaluation",
                "path": evaluation_path,
                "depends_on": [db_path, discovery_path],
                "recovery_step": "evaluate",
            },
            {
                "key": "brief",
                "label": "Brief",
                "path": brief_path,
                "depends_on": [discovery_path, evaluation_path],
                "recovery_step": "brief",
            },
        ]
    )
    statuses = {artifact["key"]: artifact["status"] for artifact in readiness["artifacts"]}
    reasons = {artifact["key"]: artifact["reason"] for artifact in readiness["artifacts"]}

    assert readiness["status"] == "partial"
    assert statuses["database"] == "ready"
    assert statuses["graph"] == "stale"
    assert statuses["discoveries"] == "missing"
    assert statuses["evaluation"] == "stale"
    assert statuses["brief"] == "stale"
    assert readiness["counts"]["missing"] == 1
    assert readiness["counts"]["stale"] == 3
    assert "older than input artifact" in reasons["graph"]
    assert "input artifact is missing" in reasons["evaluation"]


def test_artifact_readiness_summary_keeps_top_status_compact():
    assert (
        _artifact_readiness_summary(
            {
                "status": "ready",
                "counts": {"ready": 5, "missing": 0, "stale": 0, "total": 5},
            }
        )
        == "5/5 artifacts ready"
    )
    assert (
        _artifact_readiness_summary(
            {
                "status": "partial",
                "counts": {"ready": 2, "missing": 1, "stale": 2, "total": 5},
            }
        )
        == "2/5 ready | 1 missing | 2 stale"
    )


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


def test_ui_settings_read_default_query_and_result_limit_from_config(tmp_path):
    config_path = tmp_path / "default.yaml"
    config_path.write_text(
        """
version: 1
paths:
  papers_dir: data/papers
  db_path: data/processed/papers.sqlite
  graph_path: data/processed/research_graph.graphml
  discovery_path: data/processed/gaps_and_hypotheses.json
  evaluation_path: data/processed/evaluation_report.json
  golden_eval_path: data/processed/golden_eval_report.json
  brief_path: data/processed/researchnavigator_brief.md
  sample_outputs_dir: docs/sample_outputs
  screenshots_dir: docs/screenshots
pipeline:
  max_statements_per_type_per_paper: 30
  max_gaps: 10
  max_hypotheses: 10
  max_graph_nodes: 3000
  allow_graph_truncate: false
evaluation:
  min_overall_score: 0.75
  min_golden_pass_rate: 1.0
ui:
  default_search_query: default dataset query
  max_search_results: 7
""",
        encoding="utf-8",
    )

    settings = _load_ui_settings(config_path)

    assert settings == {
        "default_search_query": "default dataset query",
        "max_search_results": 7,
    }


def test_search_result_limit_returns_configured_window_and_message():
    results = [{"result_id": f"result_{index}"} for index in range(5)]

    limited_results, message = _limit_search_results(results, max_results=3)

    assert [result["result_id"] for result in limited_results] == [
        "result_0",
        "result_1",
        "result_2",
    ]
    assert message == "Showing top 3 of 5 local matches."


def test_global_safety_threshold_message_describes_warning_without_filtering():
    assert _global_safety_threshold_message({"safety_score": 0.8}, 0.7) is None
    assert _global_safety_threshold_message({}, 0.0) is None
    assert _global_safety_threshold_message({}, 0.5) == (
        "info",
        "Evaluation safety score is unavailable for the selected warning threshold.",
    )

    warning = _global_safety_threshold_message({"safety_score": 0.6}, 0.8)

    assert warning == (
        "warning",
        "Global safety score 0.6 is below the 0.8 warning threshold. Search results are still shown.",
    )


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


def test_result_card_title_prefers_research_text_over_internal_ids():
    statement_result = {
        "result_type": "statement",
        "result_id": "stmt_001",
        "statement_type": "limitation",
        "title": "limitation: stmt_001",
        "matched_text": "Evaluation uses a narrow dataset.",
    }
    gap_result = {
        "result_type": "gap",
        "result_id": "gap_001",
        "title": "gap_001",
        "matched_text": (
            "A possible research gap is suggested by a reported limitation: "
            "Cross-paper validation remains narrow."
        ),
    }
    hypothesis_result = {
        "result_type": "hypothesis",
        "result_id": "hyp_001",
        "title": "hyp_001",
        "matched_text": "A testable hypothesis could be that controlled evaluation clarifies the gap.",
    }

    assert _result_card_title(statement_result) == "Limitation: Evaluation uses a narrow dataset."
    assert _result_card_title(gap_result) == "Cross-paper validation remains narrow."
    assert _result_card_title(hypothesis_result) == "Controlled evaluation clarifies the gap."
    assert "stmt_001" not in _result_card_title(statement_result)
    assert "gap_001" not in _result_card_title(gap_result)
    assert "hyp_001" not in _result_card_title(hypothesis_result)


def test_result_card_metadata_keeps_ids_and_evidence_secondary():
    result = {
        "result_type": "hypothesis",
        "result_id": "hyp_001",
        "linked_gap_id": "gap_001",
        "evidence_statement_ids": ["stmt_001", "stmt_missing"],
        "score": 17,
        "safety_label": "speculative_research_hypothesis",
    }
    data = {"statements": [{"statement_id": "stmt_001"}]}

    tags = _result_metadata_tags(result, data, ["stmt_001", "stmt_missing"])
    tag_values = {(label, value) for label, value, _tone in tags}

    assert ("id", "hyp_001") in tag_values
    assert ("linked", "gap_001") in tag_values
    assert ("evidence", "1/2 available") in tag_values
    assert ("status", "speculative_research_hypothesis") in tag_values


def test_result_card_preview_avoids_repeating_the_title_but_shows_plan_details():
    repeated_gap = {
        "result_type": "gap",
        "matched_text": "A possible research gap is suggested by: Evaluation remains narrow.",
    }
    plan_result = {
        "result_type": "experiment_plan",
        "matched_text": "Evaluate controlled benchmarks.",
        "experiment_plan": {
            "method": "Compare the local method against a baseline.",
            "metrics": ["coverage", "robustness"],
        },
    }

    assert _result_card_preview(repeated_gap, "Evaluation remains narrow.") == ""
    assert _result_card_preview(plan_result, _result_card_title(plan_result)) == (
        "Method: Compare the local method against a baseline. | Metrics: coverage, robustness"
    )


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


def test_discovery_gap_triage_filters_and_sorts():
    gaps = [
        {
            "gap_id": "gap_a",
            "display_label": "Sparse noisy evaluation",
            "gap_text": "Sparse noisy evaluation remains limited.",
            "gap_type": "limitation",
            "source_statement_types": ["limitation"],
            "evidence_status": "evidence-linked",
            "evidence_count": 1,
            "paper_count": 1,
            "rank_score": 5,
        },
        {
            "gap_id": "gap_b",
            "display_label": "Cross-paper validation",
            "gap_text": "Cross-paper validation remains open.",
            "gap_type": "result_with_limitation",
            "source_statement_types": ["result", "future_work"],
            "evidence_status": "partial evidence",
            "evidence_count": 3,
            "paper_count": 2,
            "rank_score": 13,
        },
    ]

    filtered = _filter_gap_triage(gaps, "cross", "all", "future_work", "all", 2, 1)

    assert [gap["gap_id"] for gap in filtered] == ["gap_b"]
    assert [gap["gap_id"] for gap in _sort_gap_triage(gaps, "Paper coverage")] == ["gap_b", "gap_a"]


def test_discovery_hypothesis_triage_filters_and_sorts():
    hypotheses = [
        {
            "hypothesis_id": "hyp_a",
            "display_label": "Local evaluation may clarify a gap",
            "hypothesis_text": "Local evaluation may clarify a gap.",
            "gap_id": "gap_a",
            "linked_gap_label": "Sparse noisy evaluation",
            "linked_gap_type": "limitation",
            "confidence_level": "low",
            "safety_label": "speculative_research_hypothesis",
            "experiment_plan_available": False,
            "evidence_count": 1,
            "paper_count": 1,
            "triage_score": 8,
        },
        {
            "hypothesis_id": "hyp_b",
            "display_label": "Cross-paper validation may clarify a gap",
            "hypothesis_text": "Cross-paper validation may clarify a gap.",
            "gap_id": "gap_b",
            "linked_gap_label": "Cross-paper validation",
            "linked_gap_type": "result_with_limitation",
            "confidence_level": "medium",
            "safety_label": "speculative_research_hypothesis",
            "experiment_plan_available": True,
            "evidence_count": 2,
            "paper_count": 2,
            "triage_score": 13,
        },
    ]

    filtered = _filter_hypothesis_triage(
        hypotheses,
        "cross",
        "medium",
        "speculative_research_hypothesis",
        "result_with_limitation",
        "with plan",
        2,
        1,
    )

    assert [hypothesis["hypothesis_id"] for hypothesis in filtered] == ["hyp_b"]
    assert [hypothesis["hypothesis_id"] for hypothesis in _sort_hypothesis_triage(hypotheses, "Confidence")] == [
        "hyp_b",
        "hyp_a",
    ]
