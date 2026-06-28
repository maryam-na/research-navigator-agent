"""Search-first local Streamlit web app for ResearchNavigator Agent."""

from __future__ import annotations

import html
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import networkx as nx
import pandas as pd
import streamlit as st

from app.adk_tools import describe_agent_capabilities, planned_tool_trajectory
from app.mcp_server import MCP_SERVER_NAME, mcp_tool_manifest
from tools.graph_tools import graph_summary
from ui.data_access import (
    build_ingestion_status,
    build_research_themes,
    create_research_brief,
    evidence_for_statement_ids,
    file_presence,
    get_related_items,
    graph_to_tables,
    load_graph,
    load_json_file as load_json_file,
    load_processed_data as _load_processed_bundle,
    load_table,
    rank_gaps,
    rank_results,
    search_all,
    score_statement_quality,
)


DEFAULT_DB_PATH = Path("data/processed/papers.sqlite")
DEFAULT_GRAPH_PATH = Path("data/processed/research_graph.graphml")
DEFAULT_DISCOVERY_PATH = Path("data/processed/gaps_and_hypotheses.json")
DEFAULT_EVALUATION_PATH = Path("data/processed/evaluation_report.json")
STATEMENT_TYPES = ["all", "method", "result", "limitation", "future_work", "dataset", "background"]
RESULT_TYPES = ["all", "statements", "gaps", "hypotheses", "experiment_plans"]
PIPELINE_COMMANDS = [
    "uv run python -m scripts.ingest_papers --papers-dir data/papers --db-path data/processed/papers.sqlite --extract-statements --filter-statements --max-statements-per-type-per-paper 30",
    "uv run python -m scripts.build_graph --db-path data/processed/papers.sqlite --graph-path data/processed/research_graph.graphml",
    "uv run python -m scripts.discover_gaps --db-path data/processed/papers.sqlite --output-path data/processed/gaps_and_hypotheses.json",
    "uv run python -m scripts.evaluate_outputs --db-path data/processed/papers.sqlite --input-path data/processed/gaps_and_hypotheses.json --output-path data/processed/evaluation_report.json",
    "uv run streamlit run ui/streamlit_app.py",
]


def _inject_global_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --rn-ink: #111827;
            --rn-muted: #5b6472;
            --rn-line: #d8dee8;
            --rn-soft: #f6f8fb;
            --rn-panel: #ffffff;
            --rn-blue: #1d4ed8;
            --rn-green: #0f766e;
            --rn-amber: #b45309;
            --rn-red: #b91c1c;
        }
        .block-container {
            padding-top: 1.6rem;
            padding-bottom: 3rem;
            max-width: 1380px;
        }
        h1, h2, h3, h4 {
            letter-spacing: 0;
            color: var(--rn-ink);
        }
        div[data-testid="stTabs"] button {
            font-weight: 650;
            color: #334155;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: var(--rn-blue);
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--rn-line);
            border-radius: 8px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--rn-line);
            border-radius: 8px;
            overflow: hidden;
        }
        .rn-hero {
            border: 1px solid var(--rn-line);
            border-left: 5px solid var(--rn-blue);
            border-radius: 8px;
            padding: 22px 24px;
            background: linear-gradient(90deg, #ffffff 0%, #f8fbff 100%);
            margin-bottom: 18px;
        }
        .rn-hero-top {
            display: flex;
            justify-content: space-between;
            gap: 20px;
            align-items: flex-start;
            flex-wrap: wrap;
        }
        .rn-title {
            font-size: 2.05rem;
            line-height: 1.15;
            font-weight: 760;
            margin: 0 0 6px;
            color: var(--rn-ink);
        }
        .rn-subtitle {
            color: var(--rn-muted);
            font-size: 1.02rem;
            max-width: 780px;
            margin: 0;
        }
        .rn-pill-row {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-top: 14px;
        }
        .rn-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            border: 1px solid var(--rn-line);
            border-radius: 999px;
            padding: 5px 10px;
            background: #ffffff;
            color: #334155;
            font-size: 0.82rem;
            font-weight: 650;
            white-space: nowrap;
        }
        .rn-pill.good {
            border-color: #99f6e4;
            color: #115e59;
            background: #f0fdfa;
        }
        .rn-pill.warn {
            border-color: #fde68a;
            color: #92400e;
            background: #fffbeb;
        }
        .rn-hero-score {
            min-width: 210px;
            border: 1px solid var(--rn-line);
            border-radius: 8px;
            background: #ffffff;
            padding: 12px 14px;
        }
        .rn-score-label {
            color: var(--rn-muted);
            font-size: 0.76rem;
            font-weight: 700;
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        .rn-score-value {
            color: var(--rn-ink);
            font-size: 1.35rem;
            font-weight: 760;
            line-height: 1.1;
        }
        .rn-score-note {
            color: var(--rn-muted);
            font-size: 0.78rem;
            margin-top: 4px;
        }
        .rn-metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
            margin: 14px 0 20px;
        }
        .rn-metric-card {
            border: 1px solid var(--rn-line);
            border-radius: 8px;
            background: var(--rn-panel);
            padding: 14px 15px;
            min-height: 86px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        .rn-metric-label {
            color: var(--rn-muted);
            font-size: 0.76rem;
            font-weight: 700;
            text-transform: uppercase;
            margin-bottom: 7px;
        }
        .rn-metric-value {
            color: var(--rn-ink);
            font-size: 1.36rem;
            font-weight: 760;
            line-height: 1.15;
            overflow-wrap: anywhere;
        }
        .rn-section {
            margin-top: 6px;
            margin-bottom: 12px;
        }
        .rn-section-kicker {
            color: var(--rn-blue);
            font-size: 0.76rem;
            font-weight: 760;
            text-transform: uppercase;
            margin-bottom: 3px;
        }
        .rn-section-title {
            color: var(--rn-ink);
            font-size: 1.2rem;
            font-weight: 760;
            margin-bottom: 3px;
        }
        .rn-section-note {
            color: var(--rn-muted);
            font-size: 0.92rem;
            margin-bottom: 8px;
        }
        .rn-callout {
            border: 1px solid var(--rn-line);
            border-left: 4px solid var(--rn-green);
            border-radius: 8px;
            background: #fbfefd;
            padding: 12px 14px;
            margin: 10px 0 16px;
            color: #1f2937;
        }
        .rn-result-meta {
            color: var(--rn-muted);
            font-size: 0.82rem;
            border-top: 1px solid #eef2f7;
            padding-top: 8px;
            margin-top: 8px;
        }
        .rn-mini-label {
            color: var(--rn-muted);
            font-size: 0.76rem;
            font-weight: 700;
            text-transform: uppercase;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _format_display_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _render_header(counts: dict, evaluation: dict) -> None:
    safety = _format_display_value(evaluation.get("safety_score", "n/a"))
    grounding = _format_display_value(evaluation.get("grounding_score", "n/a"))
    failed_checks = len(evaluation.get("failed_checks", [])) if isinstance(evaluation, dict) else 0
    safety_class = "good" if failed_checks == 0 else "warn"
    status_text = "Safety checks passed" if failed_checks == 0 else "Safety review needed"
    st.markdown(
        f"""
        <div class="rn-hero">
          <div class="rn-hero-top">
            <div>
              <div class="rn-title">ResearchNavigator Agent</div>
              <p class="rn-subtitle">Local, grounded research discovery for small scientific paper collections.</p>
              <div class="rn-pill-row">
                <span class="rn-pill good">Local-first</span>
                <span class="rn-pill good">Google ADK-facing</span>
                <span class="rn-pill good">Evidence-linked</span>
                <span class="rn-pill {safety_class}">{html.escape(status_text)}</span>
              </div>
            </div>
            <div class="rn-hero-score">
              <div class="rn-score-label">Evaluation</div>
              <div class="rn-score-value">Safety {html.escape(safety)}</div>
              <div class="rn-score-note">Grounding {html.escape(grounding)} | {counts.get("statements", 0)} statements</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _section_header(title: str, note: str = "", kicker: str = "") -> None:
    kicker_html = f'<div class="rn-section-kicker">{html.escape(kicker)}</div>' if kicker else ""
    note_html = f'<div class="rn-section-note">{html.escape(note)}</div>' if note else ""
    st.markdown(
        f"""
        <div class="rn-section">
          {kicker_html}
          <div class="rn-section-title">{html.escape(title)}</div>
          {note_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def load_processed_data(db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, pd.DataFrame]:
    return {
        "papers": load_table(db_path, "papers"),
        "chunks": load_table(db_path, "chunks"),
        "statements": load_table(db_path, "statements"),
    }


def summarize_graph_from_path(path: str | Path = DEFAULT_GRAPH_PATH) -> dict:
    return graph_summary(load_graph(path))


def build_small_subgraph(graph: nx.DiGraph, max_nodes: int = 40) -> nx.DiGraph:
    selected_nodes = sorted(str(node_id) for node_id in graph.nodes())[:max_nodes]
    return graph.subgraph(selected_nodes).copy()


def dashboard_counts(
    processed_data: dict[str, pd.DataFrame],
    graph: nx.DiGraph,
    discovery: dict,
    evaluation: dict,
) -> dict:
    summary = graph_summary(graph)
    return {
        "papers": len(processed_data["papers"]),
        "chunks": len(processed_data["chunks"]),
        "statements": len(processed_data["statements"]),
        "graph_nodes": summary["nodes"],
        "graph_edges": summary["edges"],
        "gaps": len(discovery.get("gaps", [])),
        "hypotheses": len(discovery.get("hypotheses", [])),
        "safety_score": evaluation.get("safety_score", "not available"),
        "grounding_score": evaluation.get("grounding_score", "not available"),
    }


def _load_app_data() -> dict:
    return _load_processed_bundle(
        DEFAULT_DB_PATH,
        gaps_path=DEFAULT_DISCOVERY_PATH,
        evaluation_path=DEFAULT_EVALUATION_PATH,
        graph_path=DEFAULT_GRAPH_PATH,
    )


def _show_pipeline_instructions() -> None:
    st.info("Processed files are missing. Run the local backend pipeline first:")
    st.code("\n".join(PIPELINE_COMMANDS), language="bash")


def _metric_cards(items: list[tuple[str, object]], columns: int = 4) -> None:
    del columns
    cards = []
    for label, value in items:
        cards.append(
            '<div class="rn-metric-card">'
            f'<div class="rn-metric-label">{html.escape(str(label))}</div>'
            f'<div class="rn-metric-value">{html.escape(_format_display_value(value))}</div>'
            "</div>"
        )
    st.markdown(f'<div class="rn-metric-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def _result_card(result: dict, data: dict) -> None:
    related = get_related_items(
        result,
        data.get("gaps", []),
        data.get("hypotheses", []),
        data.get("experiment_plans", []),
    )
    indicator = result.get("safety_label") or "grounded locally"
    with st.container(border=True):
        top_cols = st.columns([1, 4, 1])
        top_cols[0].markdown(
            f'<div class="rn-mini-label">{html.escape(str(result.get("result_type", "")).replace("_", " ").title())}</div>',
            unsafe_allow_html=True,
        )
        top_cols[1].markdown(f"**{result.get('title', 'Result')}**")
        top_cols[2].caption(f"score {result.get('score', 0)}")
        st.write(result.get("matched_text") or result.get("evidence_snippet") or "No preview available.")
        meta = {
            "source": result.get("paper_id") or result.get("statement_id") or result.get("result_id"),
            "evidence": result.get("evidence_statement_ids") or result.get("evidence_snippet", ""),
            "linked_gap": result.get("linked_gap_id", ""),
            "indicator": indicator,
        }
        st.markdown(
            '<div class="rn-result-meta">'
            + html.escape(" | ".join(f"{key}: {value}" for key, value in meta.items() if value))
            + "</div>",
            unsafe_allow_html=True,
        )
        with st.expander("Open details"):
            st.json(
                {
                    "result": result,
                    "related_graph_nodes": _related_graph_nodes(result),
                    "related_gaps": related["gaps"],
                    "related_hypotheses": related["hypotheses"],
                    "related_experiment_plans": related["experiment_plans"],
                }
            )


def _related_graph_nodes(result: dict) -> list[str]:
    nodes = []
    statement_id = result.get("statement_id") or result.get("result_id")
    if statement_id:
        nodes.append(f"statement:{statement_id}")
        if result.get("statement_type"):
            nodes.append(f"{result['statement_type']}:{statement_id}")
    if result.get("paper_id"):
        nodes.append(f"paper:{result['paper_id']}")
    return nodes


def _flatten_results(results_by_type: dict[str, list[dict]], query: str) -> list[dict]:
    flattened = []
    for results in results_by_type.values():
        flattened.extend(results)
    return rank_results(query, flattened)


def _discovery_summary(results: list[dict]) -> None:
    statements = [item for item in results if item.get("result_type") == "statement"]
    gaps = [item for item in results if item.get("result_type") == "gap"]
    hypotheses = [item for item in results if item.get("result_type") == "hypothesis"]
    type_counts = {}
    for item in statements:
        statement_type = item.get("statement_type", "unknown")
        type_counts[statement_type] = type_counts.get(statement_type, 0) + 1
    _metric_cards(
        [
            ("Matching statements", len(statements)),
            ("Related gaps", len(gaps)),
            ("Related hypotheses", len(hypotheses)),
            ("Top statement types", ", ".join(f"{k}: {v}" for k, v in sorted(type_counts.items())) or "none"),
        ],
        columns=4,
    )


def _subgraph_for_results(graph: nx.DiGraph, results: list[dict], max_nodes: int = 50) -> nx.DiGraph:
    candidate_nodes: set[str] = set()
    for result in results:
        candidate_nodes.update(_related_graph_nodes(result))
        for evidence_id in result.get("evidence_statement_ids", []) or []:
            candidate_nodes.add(f"statement:{evidence_id}")
    existing = [node for node in candidate_nodes if node in graph]
    if not existing:
        return build_small_subgraph(graph, max_nodes=max_nodes)
    expanded = set(existing)
    for node in existing:
        expanded.update(str(neighbor) for neighbor in graph.successors(node))
        expanded.update(str(neighbor) for neighbor in graph.predecessors(node))
    selected = sorted(expanded)[:max_nodes]
    return graph.subgraph(selected).copy()


def _render_graph(graph: nx.DiGraph) -> None:
    nodes_df, edges_df = graph_to_tables(graph)
    if graph.number_of_nodes() == 0:
        st.info("No graph data available yet.")
        return
    try:
        import plotly.graph_objects as go

        positions = nx.spring_layout(graph, seed=7)
        edge_x: list[float | None] = []
        edge_y: list[float | None] = []
        for source, target in graph.edges():
            x0, y0 = positions[source]
            x1, y1 = positions[target]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines", line={"width": 1, "color": "#9ca3af"}))
        fig.add_trace(
            go.Scatter(
                x=[positions[node][0] for node in graph.nodes()],
                y=[positions[node][1] for node in graph.nodes()],
                mode="markers",
                marker={"size": 9, "color": "#2563eb"},
                text=[str(node) for node in graph.nodes()],
                hoverinfo="text",
            )
        )
        fig.update_layout(showlegend=False, margin={"l": 0, "r": 0, "t": 10, "b": 0}, height=520)
        st.plotly_chart(fig, width="stretch")
    except Exception:
        st.info("Interactive graph rendering is unavailable. Showing graph tables instead.")
    with st.expander("Node and edge tables"):
        st.dataframe(nodes_df, width="stretch")
        st.dataframe(edges_df, width="stretch")


def main() -> None:
    st.set_page_config(page_title="ResearchNavigator Agent", layout="wide")
    _inject_global_styles()
    data = _load_app_data()
    processed_data = {key: data[key] for key in ("papers", "chunks", "statements")}
    discovery = {
        "gaps": data["gaps"],
        "hypotheses": data["hypotheses"],
        "experiment_plans": data["experiment_plans"],
    }
    graph = data["graph"]
    evaluation = data["evaluation"]
    counts = dashboard_counts(processed_data, graph, discovery, evaluation)

    _render_header(counts, evaluation)
    _metric_cards(
        [
            ("Papers", counts["papers"]),
            ("Chunks", counts["chunks"]),
            ("Statements", counts["statements"]),
            ("Graph nodes", counts["graph_nodes"]),
            ("Graph edges", counts["graph_edges"]),
            ("Gaps", counts["gaps"]),
            ("Hypotheses", counts["hypotheses"]),
            ("Grounding", counts["grounding_score"]),
        ],
        columns=4,
    )

    if not DEFAULT_DB_PATH.exists():
        _show_pipeline_instructions()

    tabs = st.tabs(
        [
            "Search",
            "Evidence Inspector",
            "Discoveries",
            "Research Themes",
            "Knowledge Graph",
            "Report",
            "Safety & Evaluation",
            "Pipeline Trace",
        ]
    )

    with tabs[0]:
        _section_header(
            "Search the local research corpus",
            "Results are ranked across papers, statements, gaps, hypotheses, and experiment plans.",
            "Discovery",
        )
        query = st.text_input(
            "Research question or keyword",
            placeholder="Find research gaps related to evaluation of AI-generated hypotheses",
        )
        filter_cols = st.columns(4)
        statement_type = filter_cols[0].selectbox("Statement type", STATEMENT_TYPES)
        result_type = filter_cols[1].selectbox("Result type", RESULT_TYPES)
        min_safety_score = filter_cols[2].slider("Minimum safety score", 0.0, 1.0, 0.0, 0.1)
        paper_options = ["all"] + sorted(str(item) for item in data["papers"].get("paper_id", pd.Series(dtype=str)).dropna().unique())
        paper_id = filter_cols[3].selectbox("Paper", paper_options)
        search_clicked = st.button("Search", type="primary")

        if evaluation.get("safety_score", 0) and float(evaluation.get("safety_score", 0)) < min_safety_score:
            st.warning("Current evaluation safety score is below the selected threshold.")

        results_by_type = search_all(
            query if search_clicked or query else "",
            data,
            {
                "statement_type": statement_type,
                "result_type": result_type,
                "paper_id": paper_id,
            },
        )
        results = _flatten_results(results_by_type, query)
        if query:
            _discovery_summary(results)
            if not results:
                st.info("No local matches found. Try a broader keyword or run the processing pipeline.")
            for result in results[:30]:
                _result_card(result, data)
        else:
            st.markdown(
                """
                <div class="rn-callout">
                  <strong>Example searches</strong><br>
                  What are the limitations of AI systems for scientific discovery?<br>
                  Which papers discuss automated hypothesis generation?<br>
                  Find research gaps related to evaluation of AI-generated hypotheses.
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.session_state["last_search_results"] = results

    with tabs[1]:
        _section_header(
            "Evidence inspector",
            "Review source statements, compact evidence snippets, quality signals, and linked discoveries.",
            "Grounding",
        )
        statements = data["statements"]
        if statements.empty:
            st.info("No statements are available yet. Run ingestion with statement extraction first.")
        else:
            statement_ids = sorted(str(item) for item in statements["statement_id"].dropna().unique())
            selected_statement_id = st.selectbox("Statement", statement_ids)
            selected_statement = statements[statements["statement_id"] == selected_statement_id].iloc[0].to_dict()
            quality = score_statement_quality(selected_statement)
            _metric_cards(
                [
                    ("Grounding", quality["grounding_confidence"]),
                    ("Usefulness", quality["usefulness_score"]),
                    ("Citation risk", quality["citation_reference_risk"]),
                    ("Overall quality", quality["overall_quality"]),
                ],
                columns=4,
            )
            detail_cols = st.columns([2, 1])
            with detail_cols[0]:
                st.markdown("#### Source statement")
                st.write(selected_statement.get("statement_text"))
                st.caption(f"Paper: {selected_statement.get('paper_id')} | Chunk: {selected_statement.get('chunk_id')}")
                st.markdown("#### Evidence snippet")
                st.write(selected_statement.get("evidence_text"))
            with detail_cols[1]:
                related = get_related_items(
                    {
                        "result_type": "statement",
                        "result_id": selected_statement_id,
                        "statement_id": selected_statement_id,
                    },
                    data["gaps"],
                    data["hypotheses"],
                    data["experiment_plans"],
                )
                st.markdown("#### Linked outputs")
                st.metric("Gaps", len(related["gaps"]))
                st.metric("Hypotheses", len(related["hypotheses"]))
                st.metric("Experiment plans", len(related["experiment_plans"]))
            with st.expander("Linked details"):
                st.json(related)

    with tabs[2]:
        _metric_cards(
            [
                ("Papers", counts["papers"]),
                ("Statements", counts["statements"]),
                ("Gaps", counts["gaps"]),
                ("Hypotheses", counts["hypotheses"]),
            ],
            columns=4,
        )
        _section_header("Ranked research gaps", "Gaps are ranked by evidence count, paper coverage, and actionability.", "Discovery")
        ranked_gaps = rank_gaps(data["gaps"], data["statements"])
        for gap in ranked_gaps:
            with st.container(border=True):
                st.markdown(f"**{gap.get('gap_id')}**")
                st.caption(
                    f"Rank score: {gap.get('rank_score')} | Evidence: {gap.get('evidence_count')} statements | Papers: {gap.get('paper_count')}"
                )
                st.write(gap.get("gap_text"))
                with st.expander("Inspect evidence"):
                    evidence = evidence_for_statement_ids(gap.get("source_statement_ids", []), data["statements"])
                    st.dataframe(pd.DataFrame(evidence), width="stretch")
        _section_header("Hypotheses", "Candidate hypotheses remain speculative and linked to local evidence.", "Experiment design")
        for hypothesis in data["hypotheses"]:
            with st.container(border=True):
                st.markdown(f"**{hypothesis.get('hypothesis_id')}**")
                st.write(hypothesis.get("hypothesis_text"))
                st.caption(
                    f"Gap: {hypothesis.get('gap_id')} | Confidence: {hypothesis.get('confidence_level')} | Safety: {hypothesis.get('safety_label')}"
                )
                with st.expander("Evidence and experiment plan"):
                    evidence = evidence_for_statement_ids(hypothesis.get("evidence_statement_ids", []), data["statements"])
                    st.dataframe(pd.DataFrame(evidence), width="stretch")
                    plans = [
                        item
                        for item in data["experiment_plans"]
                        if item.get("hypothesis_id") == hypothesis.get("hypothesis_id")
                    ]
                    if plans:
                        st.json(plans[0].get("plan", {}))

    with tabs[3]:
        _section_header(
            "Research themes",
            "Deterministic clusters from recurring statement keywords and graph coverage.",
            "Synthesis",
        )
        themes = build_research_themes(data["statements"], graph)
        if not themes:
            st.info("No themes available yet.")
        else:
            theme_df = pd.DataFrame(themes)
            st.dataframe(theme_df, width="stretch")
            selected_theme = st.selectbox("Explore theme", [item["theme"] for item in themes])
            theme = next(item for item in themes if item["theme"] == selected_theme)
            evidence = evidence_for_statement_ids(theme["representative_statement_ids"], data["statements"])
            st.markdown("#### Representative evidence")
            st.dataframe(pd.DataFrame(evidence), width="stretch")

    with tabs[4]:
        search_results = st.session_state.get("last_search_results", [])
        subgraph = _subgraph_for_results(graph, search_results) if search_results else build_small_subgraph(graph)
        _section_header(
            "Knowledge graph",
            "Search-linked graph sample when results are available; otherwise an overview subgraph.",
            "Graph",
        )
        st.json(graph_summary(subgraph))
        _render_graph(subgraph)

    with tabs[5]:
        _section_header("Exportable research brief", "A local Markdown brief generated from current artifacts.", "Report")
        brief = create_research_brief(data)
        st.download_button(
            "Download Markdown brief",
            data=brief,
            file_name="researchnavigator_brief.md",
            mime="text/markdown",
        )
        st.code(brief, language="markdown")

    with tabs[6]:
        if not evaluation:
            st.info("No evaluation report found. Run the evaluation command in Pipeline Trace.")
        else:
            failed_checks = evaluation.get("failed_checks", [])
            status = "Passed" if not failed_checks and evaluation.get("safety_score", 0) >= 1.0 else "Needs review"
            _section_header(f"Safety status: {status}", "Deterministic checks for grounding, safety, testability, and traceability.", "Evaluation")
            _metric_cards(
                [
                    ("Overall", evaluation.get("overall_score", "n/a")),
                    ("Grounding", evaluation.get("grounding_score", "n/a")),
                    ("Safety", evaluation.get("safety_score", "n/a")),
                    ("Testability", evaluation.get("testability_score", "n/a")),
                    ("Traceability", evaluation.get("traceability_score", "n/a")),
                ],
                columns=5,
            )
            warnings = evaluation.get("warnings", [])
            if warnings:
                st.warning("The evaluator found caveats even if required checks passed.")
                st.dataframe(pd.DataFrame(warnings), width="stretch")
            with st.expander("Metric details"):
                st.json(evaluation.get("metric_details", {}))
            if failed_checks:
                st.error("Failed checks require review.")
                st.dataframe(pd.DataFrame(failed_checks), width="stretch")
            else:
                st.success("No deterministic safety failures detected.")

    with tabs[7]:
        agent_story = describe_agent_capabilities()
        trajectory = planned_tool_trajectory()
        _section_header("ADK agent view", "Local Google ADK-facing wrapper over deterministic research tools.", "Agent")
        story_cols = st.columns(4)
        story_cols[0].metric("Agent", agent_story["agent_name"])
        story_cols[1].metric("Framework", agent_story["agent_framework"])
        story_cols[2].metric("Callable tools", agent_story["tool_count"])
        story_cols[3].metric("Mode", agent_story["mode"])
        st.caption(agent_story["orchestration_pattern"])
        with st.expander("Agent instruction and safety boundaries", expanded=True):
            st.write(agent_story["model_policy"])
            st.dataframe(
                pd.DataFrame(
                    {
                        "course_concept": agent_story["course_concepts"],
                    }
                ),
                width="stretch",
            )
            st.dataframe(
                pd.DataFrame(
                    {
                        "safety_boundary": agent_story["safety_boundaries"],
                    }
                ),
                width="stretch",
            )
        _section_header("ADK-facing tool manifest", "Callable tools exposed through the local agent layer.", "Tools")
        st.dataframe(pd.DataFrame(agent_story["tools"]), width="stretch")
        _section_header(
            "Planned tool trajectory",
            "Deterministic orchestration path for a research-discovery request.",
            "Trajectory",
        )
        st.dataframe(pd.DataFrame(trajectory["steps"]), width="stretch")
        st.caption("Final answer contract: " + " | ".join(trajectory["final_answer_contract"]))

        mcp_manifest = mcp_tool_manifest()
        _section_header(
            "Local MCP server",
            "Selected deterministic tools are exposed to MCP-compatible clients without changing the local-first safety model.",
            "MCP",
        )
        _metric_cards(
            [
                ("MCP server", MCP_SERVER_NAME),
                ("MCP tools", len(mcp_manifest)),
                ("Run command", "make mcp"),
            ],
            columns=3,
        )
        st.dataframe(pd.DataFrame(mcp_manifest), width="stretch")
        st.code("uv run python -m scripts.run_mcp_server", language="bash")

        _section_header("Pipeline steps", "Backend processing stages and generated artifact status.", "Operations")
        status = build_ingestion_status(data)
        if not status.empty:
            _section_header("Paper ingestion status")
            st.dataframe(status, width="stretch")
        st.write(
            pd.DataFrame(
                {
                    "step": [
                        "PDF ingestion",
                        "Chunking",
                        "Statement extraction",
                        "Statement filtering",
                        "Graph building",
                        "Gap discovery",
                        "Hypothesis generation",
                        "Experiment planning",
                        "Safety evaluation",
                    ]
                }
            )
        )
        st.markdown("### Generated files")
        st.dataframe(
            file_presence([DEFAULT_DB_PATH, DEFAULT_GRAPH_PATH, DEFAULT_DISCOVERY_PATH, DEFAULT_EVALUATION_PATH]),
            width="stretch",
        )
        st.markdown("### Commands")
        st.code("\n".join(PIPELINE_COMMANDS), language="bash")
        with st.expander("Raw backend tables"):
            st.dataframe(data["papers"], width="stretch")
            st.dataframe(data["statements"], width="stretch")


if __name__ == "__main__":
    main()
