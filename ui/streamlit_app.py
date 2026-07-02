"""Search-first local Streamlit web app for ResearchNavigator Agent."""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import networkx as nx
import pandas as pd
import streamlit as st

from app.adk_tools import describe_agent_capabilities, planned_tool_trajectory
from app.mcp_server import MCP_SERVER_NAME, mcp_tool_manifest
from tools.config_tools import DEFAULT_CONFIG_PATH, load_config
from tools.graph_tools import graph_summary
from ui.corpus_setup import (
    CORPUS_MAX_PDFS,
    CORPUS_MIN_PDFS,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_PAPERS_DIR,
    describe_pdf_corpus,
    save_uploaded_pdfs,
    validate_pdf_upload_selection,
)
from ui.data_access import (
    build_artifact_readiness,
    build_evidence_chain,
    build_ingestion_status,
    build_research_themes,
    create_research_brief,
    discovery_label,
    evidence_for_statement_ids,
    file_presence,
    get_related_items,
    graph_to_tables,
    humanize_discovery_text,
    load_graph,
    load_table,
    prepare_hypothesis_triage,
    rank_gaps,
    rank_results,
    score_statement_quality,
    search_all,
)
from ui.data_access import (
    load_json_file as load_json_file,
)
from ui.data_access import (
    load_processed_data as _load_processed_bundle,
)
from ui.pipeline_runner import (
    LocalPipelineRunResult,
    run_local_pipeline,
    validate_local_pipeline_config,
)

DEFAULT_DB_PATH = Path("data/processed/papers.sqlite")
DEFAULT_GRAPH_PATH = Path("data/processed/research_graph.graphml")
DEFAULT_DISCOVERY_PATH = Path("data/processed/gaps_and_hypotheses.json")
DEFAULT_EVALUATION_PATH = Path("data/processed/evaluation_report.json")
DEFAULT_BRIEF_PATH = Path("data/processed/researchnavigator_brief.md")
DEFAULT_AGENT_TRACE_PATH = Path("data/generated/agent_trace_demo.json")
FALLBACK_DEFAULT_SEARCH_QUERY = "limitations evaluation dataset"
FALLBACK_MAX_SEARCH_RESULTS = 30
SEARCH_PAGE_SIZE_OPTIONS = [6, 10, 15, 30]
STATEMENT_TYPES = ["all", "method", "result", "limitation", "future_work", "dataset", "background"]
RESULT_TYPES = ["all", "statements", "gaps", "hypotheses", "experiment_plans"]
SELECTED_EVIDENCE_KEY = "selected_evidence_statement_id"
SELECTED_EVIDENCE_SOURCE_KEY = "selected_evidence_source"
EVIDENCE_SELECTBOX_KEY = "evidence_inspector_statement_selectbox"
SEARCH_RESULTS_PAGE_KEY = "search_results_page"
SEARCH_RESULTS_PAGE_SIZE_KEY = "search_results_page_size"
LAST_PIPELINE_RUN_KEY = "last_local_pipeline_run"
PIPELINE_COMMANDS = [
    "uv run python -m scripts.ingest_papers --papers-dir data/papers --db-path data/processed/papers.sqlite --extract-statements --filter-statements --max-statements-per-type-per-paper 30",
    "uv run python -m scripts.build_graph --db-path data/processed/papers.sqlite --graph-path data/processed/research_graph.graphml",
    "uv run python -m scripts.discover_gaps --db-path data/processed/papers.sqlite --output-path data/processed/gaps_and_hypotheses.json",
    "uv run python -m scripts.evaluate_outputs --db-path data/processed/papers.sqlite --input-path data/processed/gaps_and_hypotheses.json --output-path data/processed/evaluation_report.json",
    "uv run streamlit run ui/streamlit_app.py",
]
BRIEF_ARTIFACT_COMMAND = (
    "uv run python -m scripts.run_demo --brief-path "
    "data/processed/researchnavigator_brief.md"
)
AGENT_TRACE_COMMAND = "uv run python -m scripts.export_agent_trace"
ARTIFACT_SPECS = [
    {
        "key": "database",
        "label": "SQLite database",
        "path": DEFAULT_DB_PATH,
        "recovery_step": PIPELINE_COMMANDS[0],
    },
    {
        "key": "graph",
        "label": "Knowledge graph",
        "path": DEFAULT_GRAPH_PATH,
        "depends_on": [DEFAULT_DB_PATH],
        "recovery_step": PIPELINE_COMMANDS[1],
    },
    {
        "key": "discoveries",
        "label": "Gaps and hypotheses",
        "path": DEFAULT_DISCOVERY_PATH,
        "depends_on": [DEFAULT_DB_PATH],
        "recovery_step": PIPELINE_COMMANDS[2],
    },
    {
        "key": "evaluation",
        "label": "Evaluation report",
        "path": DEFAULT_EVALUATION_PATH,
        "depends_on": [DEFAULT_DB_PATH, DEFAULT_DISCOVERY_PATH],
        "recovery_step": PIPELINE_COMMANDS[3],
    },
    {
        "key": "brief",
        "label": "Saved research brief",
        "path": DEFAULT_BRIEF_PATH,
        "depends_on": [DEFAULT_DISCOVERY_PATH, DEFAULT_EVALUATION_PATH],
        "recovery_step": BRIEF_ARTIFACT_COMMAND,
    },
    {
        "key": "agent_trace",
        "label": "Deterministic agent trace",
        "path": DEFAULT_AGENT_TRACE_PATH,
        "depends_on": [DEFAULT_DISCOVERY_PATH, DEFAULT_EVALUATION_PATH],
        "recovery_step": AGENT_TRACE_COMMAND,
    },
]
GRAPH_NODE_TYPE_STYLES = {
    "paper": {
        "label": "Paper",
        "color": "#1d4ed8",
        "description": "Local paper source",
        "default_label": True,
        "size": 15,
    },
    "statement": {
        "label": "Evidence",
        "color": "#94a3b8",
        "description": "Extracted statement provenance",
        "default_label": False,
        "size": 6,
    },
    "method": {
        "label": "Method",
        "color": "#0f766e",
        "description": "Method statement",
        "default_label": True,
        "size": 11,
    },
    "result": {
        "label": "Result",
        "color": "#7c3aed",
        "description": "Result statement",
        "default_label": True,
        "size": 11,
    },
    "limitation": {
        "label": "Limitation",
        "color": "#b91c1c",
        "description": "Limitation evidence",
        "default_label": True,
        "size": 11,
    },
    "future_work": {
        "label": "Future Work",
        "color": "#b45309",
        "description": "Future-work evidence",
        "default_label": True,
        "size": 11,
    },
    "dataset": {
        "label": "Dataset",
        "color": "#0369a1",
        "description": "Dataset evidence",
        "default_label": True,
        "size": 11,
    },
    "background": {
        "label": "Background",
        "color": "#475569",
        "description": "Background context",
        "default_label": False,
        "size": 9,
    },
    "unknown": {
        "label": "Unknown",
        "color": "#334155",
        "description": "Unclassified node",
        "default_label": False,
        "size": 9,
    },
    "gap": {
        "label": "Gap",
        "color": "#be123c",
        "description": "Generated research gap",
        "default_label": True,
        "size": 12,
    },
    "hypothesis": {
        "label": "Hypothesis",
        "color": "#9333ea",
        "description": "Speculative hypothesis",
        "default_label": True,
        "size": 12,
    },
}
GRAPH_NODE_TYPE_ORDER = {
    node_type: index for index, node_type in enumerate(GRAPH_NODE_TYPE_STYLES)
}
GRAPH_LABEL_MODES = ["Key labels", "All labels", "No labels"]


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
        .stApp {
            background: #f7f9fc;
        }
        header[data-testid="stHeader"],
        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"] {
            display: none;
        }
        .block-container {
            padding-top: 0.85rem;
            padding-left: clamp(1rem, 4vw, 3rem);
            padding-right: clamp(1rem, 4vw, 3rem);
            padding-bottom: 3rem;
            max-width: 1240px;
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
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"],
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] p {
            color: var(--rn-blue);
        }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            border-bottom-color: var(--rn-blue);
        }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"]::before,
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"]::after {
            background: var(--rn-blue) !important;
            border-color: var(--rn-blue) !important;
        }
        div[data-testid="stSlider"] div[data-baseweb="slider"] div[role="slider"],
        div[data-testid="stSlider"] div[data-baseweb="slider"] div[style*="rgb(255, 75, 75)"],
        div[data-testid="stSlider"] div[data-baseweb="slider"] div[style*="#ff4b4b"],
        div[data-testid="stSlider"] div[data-baseweb="slider"] div[style*="#ff2b2b"] {
            background: var(--rn-blue) !important;
            border-color: var(--rn-blue) !important;
            color: var(--rn-blue) !important;
        }
        div[data-baseweb="select"] span[data-baseweb="tag"],
        div[data-baseweb="select"] div[data-baseweb="tag"] {
            background: #eff6ff !important;
            border: 1px solid #bfdbfe !important;
            color: var(--rn-blue) !important;
        }
        div[data-baseweb="select"] span[data-baseweb="tag"] span,
        div[data-baseweb="select"] div[data-baseweb="tag"] span,
        div[data-baseweb="select"] span[data-baseweb="tag"] svg,
        div[data-baseweb="select"] div[data-baseweb="tag"] svg {
            color: var(--rn-blue) !important;
            fill: currentColor !important;
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
        div[data-testid="stButton"] button[kind="primary"],
        div[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"],
        div[data-testid="stFormSubmitButton"] button[kind="primary"],
        div[data-testid="stDownloadButton"] button[kind="primary"],
        button[data-testid="stBaseButton-primaryFormSubmit"],
        button[data-testid="stBaseButton-primary"] {
            background: var(--rn-blue);
            border-color: var(--rn-blue);
            color: #ffffff;
        }
        div[data-testid="stButton"] button[kind="primary"]:hover,
        div[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"]:hover,
        div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
        div[data-testid="stDownloadButton"] button[kind="primary"]:hover,
        button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
        button[data-testid="stBaseButton-primary"]:hover {
            background: #1e40af;
            border-color: #1e40af;
            color: #ffffff;
        }
        div[data-testid="stButton"] button[kind="primary"]:focus,
        div[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"]:focus,
        div[data-testid="stFormSubmitButton"] button[kind="primary"]:focus,
        div[data-testid="stDownloadButton"] button[kind="primary"]:focus,
        button[data-testid="stBaseButton-primaryFormSubmit"]:focus,
        button[data-testid="stBaseButton-primary"]:focus {
            box-shadow: 0 0 0 0.15rem rgba(37, 99, 235, 0.24);
            outline: none;
        }
        div[data-testid="stCodeBlock"],
        div[data-testid="stCodeBlock"] pre,
        div[data-testid="stCodeBlock"] code {
            max-width: 100%;
        }
        div[data-testid="stCodeBlock"] {
            overflow: hidden;
        }
        div[data-testid="stCodeBlock"] pre {
            overflow-x: auto;
            white-space: pre;
        }
        .rn-hero {
            border: 1px solid var(--rn-line);
            border-left: 4px solid var(--rn-blue);
            border-radius: 8px;
            padding: 12px 14px;
            background: #ffffff;
            margin-bottom: 8px;
            box-shadow: 0 6px 16px rgba(15, 23, 42, 0.05);
        }
        .rn-hero-top {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(220px, 285px);
            justify-content: space-between;
            gap: 14px;
            align-items: flex-start;
        }
        .rn-kicker {
            color: var(--rn-blue);
            font-size: 0.72rem;
            font-weight: 760;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 5px;
        }
        .rn-title {
            font-size: 1.42rem;
            line-height: 1.15;
            font-weight: 760;
            margin: 0 0 3px;
            color: var(--rn-ink);
            overflow-wrap: anywhere;
        }
        .rn-subtitle {
            color: var(--rn-muted);
            font-size: 0.88rem;
            max-width: 780px;
            margin: 0;
        }
        .rn-pill-row {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
            margin-top: 6px;
        }
        .rn-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            border: 1px solid var(--rn-line);
            border-radius: 999px;
            padding: 3px 8px;
            background: #ffffff;
            color: #334155;
            font-size: 0.76rem;
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
            border: 1px solid var(--rn-line);
            border-radius: 8px;
            background: #f8fafc;
            padding: 8px 10px;
            min-width: 0;
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
            font-size: 0.98rem;
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
            gap: 10px;
            margin: 10px 0 14px;
        }
        .rn-metric-card {
            border: 1px solid var(--rn-line);
            border-radius: 8px;
            background: var(--rn-panel);
            padding: 10px 12px;
            min-height: 68px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        .rn-metric-label {
            color: var(--rn-muted);
            font-size: 0.76rem;
            font-weight: 700;
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        .rn-metric-value {
            color: var(--rn-ink);
            font-size: 1.08rem;
            font-weight: 760;
            line-height: 1.15;
            overflow-wrap: anywhere;
        }
        .rn-status-strip {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 8px;
            margin: 8px 0 10px;
        }
        .rn-status-chip {
            display: grid;
            gap: 2px;
            border: 1px solid var(--rn-line);
            border-radius: 8px;
            background: #ffffff;
            padding: 7px 9px;
            min-height: 34px;
            min-width: 0;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
        }
        .rn-status-label {
            color: var(--rn-muted);
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
        }
        .rn-status-value {
            color: var(--rn-ink);
            font-size: 0.92rem;
            font-weight: 760;
            line-height: 1.1;
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
        .rn-review-banner {
            border: 1px solid #fde68a;
            border-left: 4px solid var(--rn-amber);
            border-radius: 8px;
            background: #fffbeb;
            padding: 8px 10px;
            margin: 4px 0 8px;
            color: #1f2937;
        }
        .rn-artifact-meta {
            color: #475569;
            font-size: 0.78rem;
            font-weight: 650;
            margin-top: 3px;
        }
        .rn-review-banner.fail {
            border-color: #fecaca;
            border-left-color: var(--rn-red);
            background: #fff7f7;
        }
        .rn-review-banner.good {
            border-color: #99f6e4;
            border-left-color: var(--rn-green);
            background: #f0fdfa;
        }
        .rn-review-title {
            font-weight: 760;
            color: var(--rn-ink);
            margin-bottom: 2px;
        }
        .rn-review-text {
            color: #4b5563;
            font-size: 0.88rem;
            margin-bottom: 4px;
        }
        .rn-review-banner ul {
            margin: 4px 0 0 18px;
            padding: 0;
            color: #374151;
            font-size: 0.84rem;
        }
        .rn-result-meta {
            color: var(--rn-muted);
            font-size: 0.82rem;
            border-top: 1px solid #eef2f7;
            padding-top: 8px;
            margin-top: 8px;
        }
        .rn-card-title {
            color: var(--rn-ink);
            font-size: 0.98rem;
            font-weight: 760;
            line-height: 1.35;
            margin: 2px 0 4px;
            overflow-wrap: anywhere;
        }
        .rn-card-preview {
            color: #374151;
            font-size: 0.9rem;
            line-height: 1.45;
            margin: 4px 0 6px;
            overflow-wrap: anywhere;
        }
        .rn-mini-label {
            color: var(--rn-muted);
            font-size: 0.76rem;
            font-weight: 700;
            text-transform: uppercase;
        }
        .rn-tag-list {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin: 7px 0 8px;
        }
        .rn-tag {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            border: 1px solid var(--rn-line);
            border-radius: 999px;
            background: #f8fafc;
            color: #334155;
            padding: 3px 8px;
            font-size: 0.74rem;
            font-weight: 650;
            max-width: 100%;
        }
        .rn-tag.warn {
            border-color: #fde68a;
            color: #92400e;
            background: #fffbeb;
        }
        .rn-tag.good {
            border-color: #99f6e4;
            color: #115e59;
            background: #f0fdfa;
        }
        .rn-tag.action {
            border-color: #bfdbfe;
            color: #1d4ed8;
            background: #eff6ff;
        }
        .rn-review-strip {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 8px;
            margin: 8px 0 12px;
        }
        .rn-review-strip-item {
            border: 1px solid var(--rn-line);
            border-radius: 8px;
            background: #ffffff;
            padding: 8px 10px;
            min-width: 0;
        }
        .rn-review-strip-label {
            color: var(--rn-muted);
            font-size: 0.7rem;
            font-weight: 760;
            text-transform: uppercase;
            margin-bottom: 2px;
        }
        .rn-review-strip-value {
            color: var(--rn-ink);
            font-size: 0.86rem;
            font-weight: 700;
            line-height: 1.25;
            overflow-wrap: anywhere;
        }
        .rn-result-pager-note {
            color: var(--rn-muted);
            font-size: 0.82rem;
            margin: 4px 0 8px;
        }
        .rn-chain-note {
            color: var(--rn-muted);
            font-size: 0.86rem;
            margin: 4px 0 8px;
        }
        .rn-chain-label {
            color: var(--rn-blue);
            font-size: 0.74rem;
            font-weight: 760;
            text-transform: uppercase;
            margin-top: 10px;
        }
        .rn-chain-title {
            color: var(--rn-ink);
            font-weight: 760;
            margin: 2px 0 3px;
        }
        .rn-chain-meta {
            color: var(--rn-muted);
            font-size: 0.78rem;
            margin-bottom: 5px;
        }
        .rn-evidence-panel {
            border: 1px solid #bfdbfe;
            border-left: 4px solid var(--rn-blue);
            border-radius: 8px;
            background: #f8fbff;
            padding: 10px 12px;
            margin: 8px 0 10px;
        }
        .rn-evidence-panel-title {
            color: var(--rn-ink);
            font-weight: 760;
            line-height: 1.3;
            margin: 2px 0 5px;
            overflow-wrap: anywhere;
        }
        .rn-evidence-panel-meta {
            color: var(--rn-muted);
            font-size: 0.78rem;
            font-weight: 650;
            margin-bottom: 7px;
            overflow-wrap: anywhere;
        }
        .rn-evidence-panel-subhead {
            color: var(--rn-blue);
            font-size: 0.72rem;
            font-weight: 760;
            text-transform: uppercase;
            margin-top: 8px;
        }
        .rn-evidence-panel-text {
            color: #374151;
            font-size: 0.88rem;
            line-height: 1.45;
            margin-top: 2px;
            overflow-wrap: anywhere;
        }
        .rn-graph-legend {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin: 8px 0 10px;
        }
        .rn-graph-legend-item {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            border: 1px solid var(--rn-line);
            border-radius: 999px;
            background: #ffffff;
            color: #334155;
            padding: 4px 8px;
            font-size: 0.74rem;
            font-weight: 650;
            max-width: 100%;
        }
        .rn-graph-dot {
            width: 9px;
            height: 9px;
            border-radius: 999px;
            flex: 0 0 auto;
        }
        div[data-testid="stTabs"] div[role="tablist"] {
            gap: 4px;
            flex-wrap: wrap;
            overflow-x: visible;
        }
        div[data-testid="stTabs"] button[role="tab"] {
            min-height: 2.15rem;
            padding: 0.35rem 0.55rem;
            border-radius: 6px 6px 0 0;
        }
        div[data-testid="stTabs"] button[role="tab"] p {
            white-space: normal;
        }
        @media (max-width: 700px) {
            .block-container {
                padding: 0.75rem 0.65rem 2rem;
            }
            .rn-hero {
                padding: 10px;
                margin-bottom: 6px;
            }
            .rn-hero-top {
                grid-template-columns: minmax(0, 1fr);
                gap: 8px;
            }
            .rn-kicker {
                font-size: 0.66rem;
                margin-bottom: 4px;
            }
            .rn-title {
                font-size: 1.22rem;
            }
            .rn-subtitle {
                font-size: 0.8rem;
            }
            .rn-pill-row {
                display: none;
            }
            .rn-hero-score {
                width: 100%;
                padding: 7px 8px;
            }
            .rn-score-label,
            .rn-score-note {
                font-size: 0.7rem;
            }
            .rn-score-value {
                font-size: 0.95rem;
            }
            .rn-status-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 6px;
                margin: 6px 0 8px;
            }
            .rn-status-chip {
                padding: 5px 7px;
            }
            .rn-status-chip:last-child {
                grid-column: 1 / -1;
            }
            .rn-status-label {
                font-size: 0.66rem;
            }
            .rn-status-value {
                font-size: 0.82rem;
            }
            .rn-review-banner {
                padding: 8px 9px;
            }
            .rn-review-banner ul {
                display: none;
            }
            .rn-tag {
                font-size: 0.68rem;
                padding: 3px 6px;
            }
            .rn-graph-legend-item {
                font-size: 0.68rem;
                padding: 3px 6px;
            }
            div[data-testid="stTabs"] div[role="tablist"] {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 4px;
            }
            div[data-testid="stTabs"] button[role="tab"] {
                width: 100%;
                min-width: 0;
                min-height: 2rem;
                padding: 0.28rem 0.25rem;
                justify-content: center;
            }
            div[data-testid="stTabs"] button[role="tab"] p {
                font-size: 0.74rem;
                line-height: 1.05;
            }
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
    status = evaluation_status_summary(evaluation)
    safety = status["safety_label"]
    grounding = status["grounding_label"]
    corpus_note = f"{counts.get('papers', 0)} papers | {counts.get('statements', 0)} statements"
    st.markdown(
        f"""
        <div class="rn-hero">
          <div class="rn-hero-top">
            <div>
              <div class="rn-kicker">Local research workspace</div>
              <div class="rn-title">ResearchNavigator Agent</div>
              <p class="rn-subtitle">Capstone demo: local, privacy-preserving research discovery with evidence-linked agent tools.</p>
              <div class="rn-pill-row">
                <span class="rn-pill good">Local-first</span>
                <span class="rn-pill good">Google ADK-facing</span>
                <span class="rn-pill good">Evidence-linked</span>
                <span class="rn-pill {status["tone"]}">{html.escape(status["pill_text"])}</span>
              </div>
            </div>
            <div class="rn-hero-score">
              <div class="rn-score-label">Evaluation</div>
              <div class="rn-score-value">{html.escape(status["headline"])}</div>
              <div class="rn-score-note">{html.escape(corpus_note)}</div>
              <div class="rn-score-note">Safety {html.escape(safety)} | Grounding {html.escape(grounding)}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_status_strip(counts: dict, evaluation: dict) -> None:
    status = evaluation_status_summary(evaluation)
    items = [
        ("Papers", counts.get("papers", 0)),
        ("Statements", counts.get("statements", 0)),
        ("Gaps / Hypotheses", f"{counts.get('gaps', 0)} / {counts.get('hypotheses', 0)}"),
        ("Grounding", counts.get("grounding_score", "n/a")),
        ("Evaluation", status["headline"]),
    ]
    chips = []
    for label, value in items:
        chips.append(
            '<span class="rn-status-chip">'
            f'<span class="rn-status-label">{html.escape(str(label))}</span>'
            f'<span class="rn-status-value">{html.escape(_format_display_value(value))}</span>'
            "</span>"
        )
    st.markdown(f'<div class="rn-status-strip">{"".join(chips)}</div>', unsafe_allow_html=True)


def _artifact_readiness_summary(readiness: dict[str, object]) -> str:
    counts = dict(readiness.get("counts", {}) or {})
    ready = counts.get("ready", 0)
    missing = counts.get("missing", 0)
    stale = counts.get("stale", 0)
    total = counts.get("total", 0)
    if readiness.get("status") == "ready":
        return f"{ready}/{total} artifacts ready"
    parts = [f"{ready}/{total} ready"]
    if missing:
        parts.append(f"{missing} missing")
    if stale:
        parts.append(f"{stale} stale")
    return " | ".join(parts)


def _artifact_readiness_display_summary(readiness: dict[str, object]) -> str:
    status = str(readiness.get("status", "partial"))
    if status == "ready":
        return str(readiness.get("summary", "All expected local generated artifacts are present and current enough."))
    if status == "missing":
        return (
            "Processed files are missing. Use Pipeline Trace to run local recovery commands "
            "or rebuild the pipeline."
        )
    return (
        "Some generated files are missing or older than their inputs. "
        "Recovery commands are consolidated in Pipeline Trace."
    )


def _render_artifact_readiness(
    readiness: dict[str, object],
    *,
    include_details: bool = True,
) -> None:
    status = str(readiness.get("status", "partial"))
    banner_class = _artifact_banner_class(status)
    headline = html.escape(str(readiness.get("headline", "Artifact readiness")))
    summary = html.escape(_artifact_readiness_display_summary(readiness))
    artifact_summary = html.escape(_artifact_readiness_summary(readiness))
    st.markdown(
        f"""
        <div class="rn-review-banner {banner_class}">
          <div class="rn-review-title">{headline}</div>
          <div class="rn-review-text">{summary}</div>
          <div class="rn-artifact-meta">{artifact_summary}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if include_details:
        _render_artifact_readiness_details(readiness)


def _render_artifact_readiness_details(readiness: dict[str, object]) -> None:
    artifacts = list(readiness.get("artifacts", []) or [])
    problem_artifacts = list(readiness.get("problem_artifacts", []) or [])
    counts = dict(readiness.get("counts", {}) or {})
    if problem_artifacts:
        _metric_cards(
            [
                ("Ready", counts.get("ready", 0)),
                ("Missing", counts.get("missing", 0)),
                ("Stale", counts.get("stale", 0)),
                ("Expected", counts.get("total", 0)),
            ],
            columns=4,
        )
        _render_artifact_status_table(readiness)
    else:
        if artifacts:
            st.caption("All expected local artifacts are ready enough for the current inputs.")
        _render_artifact_status_table(readiness)


def _artifact_guidance_message(artifact: dict) -> dict[str, str]:
    status = str(artifact.get("status", "not ready"))
    label = str(artifact.get("label", "Artifact"))
    reason = str(artifact.get("reason", "")).strip()
    if status == "missing":
        tone = "fail"
    elif status == "ready":
        tone = "good"
    else:
        tone = "warn"
    return {
        "tone": tone,
        "title": f"{label} is {status}",
        "body": (
            f"{reason} Recovery commands are consolidated in Pipeline Trace."
            if reason
            else "Recovery commands are consolidated in Pipeline Trace."
        ),
    }


def _render_artifact_guidance(readiness: dict[str, object], artifact_key: str) -> None:
    artifact = _artifact_by_key(readiness, artifact_key)
    if not artifact or artifact.get("status") == "ready":
        return
    message = _artifact_guidance_message(artifact)
    st.markdown(
        f"""
        <div class="rn-review-banner {html.escape(message["tone"])}">
          <div class="rn-review-title">{html.escape(message["title"])}</div>
          <div class="rn-review-text">{html.escape(message["body"])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _artifact_recovery_steps(artifacts: list[dict]) -> list[str]:
    steps = []
    for artifact in artifacts:
        step = str(artifact.get("recovery_step", "")).strip()
        if step and step not in steps:
            steps.append(step)
    return steps


def _render_recovery_steps(artifacts: list[dict], heading: str | None = "#### Recovery commands") -> None:
    steps = _artifact_recovery_steps(artifacts)
    if not steps:
        return
    if heading:
        st.markdown(heading)
    st.code("\n".join(steps), language="bash")


def _render_artifact_recovery_panel(readiness: dict[str, object]) -> None:
    problem_artifacts = list(readiness.get("problem_artifacts", []) or [])
    if not problem_artifacts:
        st.caption("No artifact recovery commands are needed for the current files.")
        return
    with st.expander("Artifact recovery commands", expanded=True):
        st.caption(
            "Run these local commands from the repository root, or use the Run local pipeline button below."
        )
        _render_recovery_steps(problem_artifacts, heading=None)


def _render_artifact_status_table(readiness: dict[str, object]) -> None:
    artifacts = list(readiness.get("artifacts", []) or [])
    rows = [
        {
            "artifact": item.get("label", ""),
            "status": item.get("status", ""),
            "path": item.get("path", ""),
            "size_bytes": item.get("size_bytes", 0),
            "modified": item.get("modified", ""),
            "reason": item.get("reason", ""),
        }
        for item in artifacts
    ]
    _render_dataframe(pd.DataFrame(rows))


def _clear_app_data_cache() -> None:
    clear = getattr(_load_app_data, "clear", None)
    if callable(clear):
        clear()


def _render_pipeline_run_control(section_key: str) -> None:
    validation = validate_local_pipeline_config(DEFAULT_CONFIG_PATH)
    with st.container(border=True):
        st.markdown("#### Run local pipeline")
        for warning in validation.warnings:
            st.warning(warning)
        for error in validation.errors:
            st.error(error)
        reset_existing = st.checkbox(
            "Reset processed artifacts before running",
            value=True,
            key=f"{section_key}-reset-pipeline",
            help="Matches `make demo` behavior by rebuilding local processed outputs.",
        )
        button_cols = st.columns([1, 3])
        run_clicked = button_cols[0].button(
            "Run local pipeline",
            type="primary",
            disabled=not validation.ok,
            key=f"{section_key}-run-pipeline",
        )
        button_cols[1].caption(
            "Runs ingestion, graph building, gap discovery, evaluation, "
            "and brief generation locally."
        )
        last_result = st.session_state.get(LAST_PIPELINE_RUN_KEY)
        if isinstance(last_result, LocalPipelineRunResult):
            _render_pipeline_run_result(last_result)
        if run_clicked:
            status = st.status("Running local pipeline...", expanded=True)

            def show_progress(_stage: str, message: str) -> None:
                status.write(message)

            with status:
                result = run_local_pipeline(
                    config_path=DEFAULT_CONFIG_PATH,
                    reset=reset_existing,
                    progress_callback=show_progress,
                )
                st.session_state[LAST_PIPELINE_RUN_KEY] = result
                if result.ok:
                    _clear_app_data_cache()
                    status.update(label="Local pipeline completed.", state="complete")
                    st.rerun()
                status.update(label="Local pipeline failed.", state="error")
                _render_pipeline_run_result(result)


def _render_pipeline_run_result(result: LocalPipelineRunResult) -> None:
    if result.ok:
        st.success(result.message)
    else:
        st.error(result.message)
    for warning in result.warnings:
        st.warning(warning)
    for error in result.errors:
        st.error(error)
    if result.summary:
        _metric_cards(
            [
                ("Papers", result.summary.get("papers", "n/a")),
                ("Statements", result.summary.get("saved_statements", "n/a")),
                ("Graph nodes", result.summary.get("graph", {}).get("nodes", "n/a")),
                ("Gaps", result.summary.get("discovery_counts", {}).get("gaps", "n/a")),
                (
                    "Hypotheses",
                    result.summary.get("discovery_counts", {}).get("hypotheses", "n/a"),
                ),
                (
                    "Overall score",
                    result.summary.get("evaluation", {}).get("overall_score", "n/a"),
                ),
            ],
            columns=3,
        )
        with st.expander("Pipeline summary", expanded=False):
            st.json(result.summary)
    if result.artifact_paths:
        with st.expander("Regenerated artifact paths", expanded=False):
            st.json(result.artifact_paths)


def _artifact_by_key(readiness: dict[str, object], artifact_key: str) -> dict | None:
    for artifact in list(readiness.get("artifacts", []) or []):
        if artifact.get("key") == artifact_key:
            return artifact
    return None


def _artifact_banner_class(status: str) -> str:
    if status == "ready":
        return "good"
    if status == "missing":
        return "fail"
    return "warn"


def evaluation_status_summary(evaluation: dict | None) -> dict[str, object]:
    """Classify evaluation display state without implying scientific proof."""

    if not evaluation:
        return {
            "key": "missing",
            "tone": "warn",
            "pill_text": "Evaluation pending",
            "headline": "Evaluation pending",
            "summary": "Run the local evaluation before treating generated outputs as reviewed.",
            "safety_label": "n/a",
            "grounding_label": "n/a",
            "failed_count": 0,
            "warning_count": 0,
            "has_grounding_caveat": False,
        }

    failed_count = len(evaluation.get("failed_checks", []) or [])
    warnings = _evaluation_warnings(evaluation)
    grounding_score = _score_to_float(evaluation.get("grounding_score"))
    has_grounding_caveat = grounding_score is not None and grounding_score < 1.0
    base = {
        "safety_label": _format_display_value(evaluation.get("safety_score", "n/a")),
        "grounding_label": _format_display_value(evaluation.get("grounding_score", "n/a")),
        "failed_count": failed_count,
        "warning_count": len(warnings),
        "has_grounding_caveat": has_grounding_caveat,
    }
    if failed_count:
        return {
            **base,
            "key": "failed",
            "tone": "warn",
            "pill_text": "Safety review needed",
            "headline": "Safety review needed",
            "summary": (
                f"{failed_count} deterministic check{'s' if failed_count != 1 else ''} "
                "need review before using generated outputs."
            ),
        }
    if warnings or has_grounding_caveat:
        return {
            **base,
            "key": "caveats",
            "tone": "warn",
            "pill_text": "Review caveats",
            "headline": "Checks passed with caveats",
            "summary": (
                "No deterministic safety failures were found, but grounding and evaluator "
                "caveats still need human review; hypotheses remain speculative."
            ),
        }
    return {
        **base,
        "key": "passed",
        "tone": "good",
        "pill_text": "Checks passed",
        "headline": "Checks passed",
        "summary": "No deterministic safety failures or evaluator caveats were found.",
    }


def _evaluation_warnings(evaluation: dict | None) -> list[dict[str, str]]:
    if not evaluation:
        return []
    raw_warnings = list(evaluation.get("warnings", []) or [])
    metric_details = evaluation.get("metric_details", {})
    if isinstance(metric_details, dict):
        raw_warnings.extend(metric_details.get("warnings", []) or [])
    warnings = []
    seen: set[tuple[str, str]] = set()
    for warning in raw_warnings:
        if isinstance(warning, dict):
            level = str(warning.get("level", "warning"))
            message = str(warning.get("message", "")).strip()
        else:
            level = "warning"
            message = str(warning).strip()
        if not message:
            continue
        key = (level, message)
        if key in seen:
            continue
        seen.add(key)
        warnings.append({"level": level, "message": message})
    return warnings


def _evaluation_caveat_items(evaluation: dict | None) -> list[str]:
    if not evaluation:
        return ["Evaluation artifacts are missing; run the local evaluation command."]
    items = []
    grounding_score = _score_to_float(evaluation.get("grounding_score"))
    if grounding_score is not None and grounding_score < 1.0:
        items.append(
            f"Grounding score is {_format_display_value(grounding_score)}; keep outputs tied to local evidence IDs."
        )
    for warning in _evaluation_warnings(evaluation):
        items.append(warning["message"])
    return items


def _score_to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _render_evaluation_caveats(evaluation: dict | None) -> None:
    status = evaluation_status_summary(evaluation)
    if status["key"] == "passed":
        return
    caveats = _evaluation_caveat_items(evaluation)
    limited_items = caveats[:3]
    if len(caveats) > len(limited_items):
        limited_items.append(f"{len(caveats) - len(limited_items)} more caveat(s) in Safety & Evaluation.")
    item_markup = "".join(f"<li>{html.escape(item)}</li>" for item in limited_items)
    banner_class = "fail" if status["key"] == "failed" else "warn"
    st.markdown(
        f"""
        <div class="rn-review-banner {banner_class}">
          <div class="rn-review-title">{html.escape(str(status["headline"]))}</div>
          <div class="rn-review-text">{html.escape(str(status["summary"]))}</div>
          <ul>{item_markup}</ul>
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
    if max_nodes <= 0:
        return nx.DiGraph()
    selected_nodes: list[str] = []
    selected_lookup: set[str] = set()
    for source, target, _attrs in _sorted_graph_edges(graph):
        if len(selected_lookup) >= max_nodes:
            break
        for node_id in (str(source), str(target)):
            if node_id in selected_lookup:
                continue
            if len(selected_lookup) >= max_nodes:
                break
            selected_lookup.add(node_id)
            selected_nodes.append(node_id)
    if not selected_nodes:
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


def _is_legacy_streamlit_width_error(error: TypeError) -> bool:
    return "'str' object cannot be interpreted as an integer" in str(error)


def _render_dataframe(data: object) -> None:
    try:
        st.dataframe(data, width="stretch")
    except TypeError as error:
        if not _is_legacy_streamlit_width_error(error):
            raise
        st.dataframe(data, use_container_width=True)


def _render_plotly_chart(fig: object) -> None:
    try:
        st.plotly_chart(fig, width="stretch")
    except TypeError as error:
        if not _is_legacy_streamlit_width_error(error):
            raise
        st.plotly_chart(fig, use_container_width=True)


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


def _load_ui_settings(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, int | str]:
    """Load intentional UI defaults from config, falling back to safe local values."""

    try:
        ui_config = load_config(config_path).ui
    except (FileNotFoundError, ValueError):
        return {
            "default_search_query": FALLBACK_DEFAULT_SEARCH_QUERY,
            "max_search_results": FALLBACK_MAX_SEARCH_RESULTS,
        }
    return {
        "default_search_query": ui_config.default_search_query,
        "max_search_results": ui_config.max_search_results,
    }


def _limit_search_results(results: list[dict], max_results: int) -> tuple[list[dict], str | None]:
    limited_results = results[:max_results]
    if len(results) <= max_results:
        return limited_results, None
    return limited_results, f"Showing top {len(limited_results)} of {len(results)} local matches."


def _search_page_size_options(max_results: int) -> list[int]:
    max_results = max(1, int(max_results))
    options = [option for option in SEARCH_PAGE_SIZE_OPTIONS if option < max_results]
    options.append(max_results)
    return sorted(set(options))


def _paginate_search_results(
    results: list[dict],
    page: int,
    page_size: int,
) -> tuple[list[dict], int, int]:
    if not results:
        return [], 1, 1
    page_size = max(1, int(page_size))
    page_count = max(1, (len(results) + page_size - 1) // page_size)
    current_page = max(1, min(int(page), page_count))
    start = (current_page - 1) * page_size
    return results[start : start + page_size], current_page, page_count


def _search_page_note(
    visible_count: int,
    total_count: int,
    current_page: int,
    page_count: int,
) -> str:
    if total_count == 0:
        return "No results to review."
    page_fragment = f"page {current_page} of {page_count}" if page_count > 1 else "single page"
    return f"Showing {visible_count} of {total_count} retained results on {page_fragment}."


def _global_safety_threshold_message(
    evaluation: dict,
    threshold: float,
) -> tuple[str, str] | None:
    if threshold <= 0:
        return None
    raw_score = evaluation.get("safety_score")
    if raw_score is None:
        return "info", "Evaluation safety score is unavailable for the selected warning threshold."
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return "info", "Evaluation safety score is unavailable for the selected warning threshold."
    if score >= threshold:
        return None
    return (
        "warning",
        (
            f"Global safety score {_format_display_value(score)} is below the "
            f"{_format_display_value(threshold)} warning threshold. Search results are still shown."
        ),
    )


def _statement_records(statements: pd.DataFrame | list[dict]) -> list[dict]:
    if isinstance(statements, pd.DataFrame):
        return statements.to_dict("records")
    return list(statements)


def _statement_lookup_from_data(data: dict) -> dict[str, dict]:
    return {
        str(statement.get("statement_id", "")): statement
        for statement in _statement_records(data.get("statements", pd.DataFrame()))
        if statement.get("statement_id")
    }


def _unique_statement_ids(statement_ids: list[object]) -> list[str]:
    unique_ids = []
    seen: set[str] = set()
    for statement_id in statement_ids:
        normalized = str(statement_id or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_ids.append(normalized)
    return unique_ids


def _evidence_statement_ids_for_result(result: dict, data: dict) -> list[str]:
    candidates: list[object] = []
    if result.get("statement_id"):
        candidates.append(result["statement_id"])
    if result.get("evidence_statement_ids"):
        candidates.extend(result.get("evidence_statement_ids", []))
    related = get_related_items(
        result,
        data.get("gaps", []),
        data.get("hypotheses", []),
        data.get("experiment_plans", []),
    )
    for gap in related["gaps"]:
        candidates.extend(gap.get("source_statement_ids", []))
    for hypothesis in related["hypotheses"]:
        candidates.extend(hypothesis.get("evidence_statement_ids", []))
    return _unique_statement_ids(candidates)


def _available_statement_ids(statement_ids: list[str], data: dict) -> list[str]:
    lookup = _statement_lookup_from_data(data)
    return [statement_id for statement_id in statement_ids if statement_id in lookup]


def _statement_option_label(statement: dict, max_chars: int = 86) -> str:
    statement_id = str(statement.get("statement_id", ""))
    statement_type = str(statement.get("statement_type", "statement")) or "statement"
    paper_id = str(statement.get("paper_id", "unknown paper")) or "unknown paper"
    text = str(statement.get("statement_text") or statement.get("evidence_text") or "")
    preview = " ".join(text.split())
    if len(preview) > max_chars:
        preview = preview[: max_chars - 3].rstrip() + "..."
    if not preview:
        preview = "No statement preview available"
    return f"{statement_type} | {paper_id} | {preview} ({statement_id})"


def _normalize_card_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clip_card_text(value: object, max_chars: int = 180) -> str:
    text = _normalize_card_text(value)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _result_type_label(result: dict) -> str:
    return str(result.get("result_type", "result")).replace("_", " ").title()


def _result_card_title(result: dict, max_chars: int = 132) -> str:
    result_type = str(result.get("result_type", "result"))
    raw_title = _normalize_card_text(result.get("title") or result.get("result_id") or "Result")
    matched_text = _normalize_card_text(result.get("matched_text") or result.get("evidence_snippet"))

    if result_type == "statement":
        statement_type = str(result.get("statement_type") or "statement").replace("_", " ").title()
        title_text = matched_text or "Statement preview unavailable"
        return _clip_card_text(f"{statement_type}: {title_text}", max_chars)
    if result_type == "gap":
        return discovery_label(matched_text, fallback="Research gap", max_chars=max_chars)
    if result_type == "hypothesis":
        return discovery_label(matched_text, fallback="Hypothesis", max_chars=max_chars)
    if result_type == "experiment_plan":
        plan = result.get("experiment_plan", {}) or {}
        objective = matched_text or _normalize_card_text(plan.get("objective"))
        if objective:
            return _clip_card_text(f"Experiment plan: {objective}", max_chars)
        return "Experiment plan"
    return _clip_card_text(raw_title, max_chars)


def _result_card_preview(result: dict, title: str, max_chars: int = 240) -> str:
    result_type = str(result.get("result_type", "result"))
    if result_type in {"gap", "hypothesis"}:
        preview = humanize_discovery_text(
            str(result.get("matched_text") or ""),
            fallback="",
        )
    elif result_type == "experiment_plan":
        plan = result.get("experiment_plan", {}) or {}
        method = _normalize_card_text(plan.get("method"))
        baseline = _normalize_card_text(plan.get("baseline_or_control"))
        metrics = plan.get("metrics", [])
        metric_text = ", ".join(str(item) for item in metrics) if isinstance(metrics, list) else str(metrics or "")
        parts = []
        if method:
            parts.append(f"Method: {method}")
        if baseline:
            parts.append(f"Control: {baseline}")
        if metric_text:
            parts.append(f"Metrics: {metric_text}")
        preview = " | ".join(parts)
    else:
        preview = _normalize_card_text(result.get("evidence_snippet") or result.get("matched_text"))

    preview = _clip_card_text(preview, max_chars)
    title_text = _normalize_card_text(title)
    if not preview or preview.lower() == title_text.lower() or title_text.lower().endswith(preview.lower()):
        return ""
    return preview


def _evidence_status_label(statement_ids: list[str], data: dict) -> str:
    if not statement_ids:
        return ""
    available_count = len(_available_statement_ids(statement_ids, data))
    total_count = len(statement_ids)
    if available_count == total_count:
        return f"{total_count} linked"
    if available_count > 0:
        return f"{available_count}/{total_count} available"
    return "IDs unavailable"


def _result_metadata_tags(
    result: dict,
    data: dict,
    evidence_statement_ids: list[str],
) -> list[tuple[str, object, str]]:
    result_type = str(result.get("result_type", "result"))
    result_id = result.get("statement_id") or result.get("result_id") or result.get("linked_hypothesis_id")
    score = result.get("score")
    linked_id = result.get("linked_gap_id") or result.get("gap_id") or result.get("linked_hypothesis_id")
    paper = result.get("paper_id")
    indicator = result.get("safety_label") or ("grounded locally" if result_type != "paper" else "")
    evidence_label = _evidence_status_label(evidence_statement_ids, data)
    indicator_tone = "warn" if str(indicator).startswith("speculative") else "good"

    return [
        ("type", _result_type_label(result), ""),
        ("score", score, ""),
        ("id", result_id, ""),
        ("paper", paper, ""),
        ("evidence", evidence_label, "good" if evidence_label.endswith("linked") else "warn"),
        ("linked", linked_id, ""),
        ("status", indicator, indicator_tone),
    ]


def _discovery_body_text(record: dict, field: str, fallback: str) -> str:
    return humanize_discovery_text(str(record.get(field, "")), fallback=fallback)


def _select_evidence_statement(statement_id: str, source_label: str) -> None:
    st.session_state[SELECTED_EVIDENCE_KEY] = statement_id
    st.session_state[SELECTED_EVIDENCE_SOURCE_KEY] = source_label


def _statement_result_payload(statement_id: str, statement: dict) -> dict:
    statement_text = statement.get("statement_text", "")
    return {
        "result_type": "statement",
        "result_id": statement_id,
        "statement_id": statement_id,
        "title": _clip_card_text(statement_text or statement_id, 96),
        "matched_text": statement_text,
        "evidence_statement_ids": [statement_id],
        "paper_id": statement.get("paper_id", ""),
        "statement_type": statement.get("statement_type", ""),
    }


def _selected_evidence_detail(data: dict, statement_id: str) -> dict:
    normalized_id = str(statement_id or "").strip()
    if not normalized_id:
        return {
            "status": "empty",
            "message": "No evidence statement is selected yet.",
        }
    statement_lookup = _statement_lookup_from_data(data)
    statement = statement_lookup.get(normalized_id)
    if not statement:
        return {
            "status": "missing",
            "statement_id": normalized_id,
            "message": "Selected evidence is not available in the current statement table.",
        }
    statement = dict(statement)
    statement["statement_id"] = str(statement.get("statement_id") or normalized_id)
    selected_result = _statement_result_payload(normalized_id, statement)
    related = get_related_items(
        selected_result,
        data.get("gaps", []),
        data.get("hypotheses", []),
        data.get("experiment_plans", []),
    )
    return {
        "status": "available",
        "statement_id": normalized_id,
        "statement": statement,
        "quality": score_statement_quality(statement),
        "result": selected_result,
        "related": related,
        "chain": build_evidence_chain(selected_result, data),
    }


def _selected_evidence_source_matches(statement_id: str, source_label: str) -> bool:
    return (
        st.session_state.get(SELECTED_EVIDENCE_KEY) == statement_id
        and st.session_state.get(SELECTED_EVIDENCE_SOURCE_KEY) == source_label
    )


def _selected_evidence_review_value(data: dict, statement_id: str) -> str:
    detail = _selected_evidence_detail(data, statement_id)
    if detail["status"] == "empty":
        return "No evidence selected"
    if detail["status"] == "missing":
        return f"{detail['statement_id']} unavailable"
    statement = detail["statement"]
    return " | ".join(
        item
        for item in [
            str(detail["statement_id"]),
            str(statement.get("statement_type", "unknown")),
            str(statement.get("paper_id", "unknown")),
        ]
        if item
    )


def _render_search_review_strip(
    data: dict,
    visible_count: int,
    total_count: int,
    current_page: int,
    page_count: int,
) -> None:
    selected_value = _selected_evidence_review_value(
        data,
        str(st.session_state.get(SELECTED_EVIDENCE_KEY, "") or ""),
    )
    items = [
        ("Results in view", _search_page_note(visible_count, total_count, current_page, page_count)),
        ("Selected evidence", selected_value),
        ("Graph focus", "Latest search results drive the graph preview"),
    ]
    markup = []
    for label, value in items:
        markup.append(
            '<div class="rn-review-strip-item">'
            f'<div class="rn-review-strip-label">{html.escape(label)}</div>'
            f'<div class="rn-review-strip-value">{html.escape(value)}</div>'
            "</div>"
        )
    st.markdown(f'<div class="rn-review-strip">{"".join(markup)}</div>', unsafe_allow_html=True)


def _render_selected_evidence_handoff(data: dict, statement_id: str, source_label: str) -> bool:
    detail = _selected_evidence_detail(data, statement_id)
    if detail["status"] == "empty":
        return False
    if detail["status"] == "missing":
        st.warning(f"{detail['message']} Statement ID: {detail['statement_id']}.")
        return False

    statement = detail["statement"]
    statement_text = _clip_card_text(statement.get("statement_text", ""), 360)
    evidence_text = _clip_card_text(statement.get("evidence_text", ""), 360)
    title = _clip_card_text(statement_text or statement_id, 120)
    meta = " | ".join(
        item
        for item in [
            f"Selected from {source_label}" if source_label else "",
            f"Statement {detail['statement_id']}",
            f"Type {statement.get('statement_type', 'unknown')}",
            f"Paper {statement.get('paper_id', 'unknown')}",
            f"Chunk {statement.get('chunk_id', 'unknown')}",
        ]
        if item
    )
    st.markdown(
        f"""
        <div class="rn-evidence-panel">
          <div class="rn-mini-label">Selected evidence inspector</div>
          <div class="rn-evidence-panel-title">{html.escape(title)}</div>
          <div class="rn-evidence-panel-meta">{html.escape(meta)}</div>
          <div class="rn-evidence-panel-subhead">Source statement</div>
          <div class="rn-evidence-panel-text">{html.escape(statement_text or "No statement text available.")}</div>
          <div class="rn-evidence-panel-subhead">Evidence snippet</div>
          <div class="rn-evidence-panel-text">{html.escape(evidence_text or "No evidence snippet available.")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return True


def _render_selected_evidence_inspector(data: dict, statement_id: str, source_label: str | None = None) -> bool:
    detail = _selected_evidence_detail(data, statement_id)
    if detail["status"] == "empty":
        st.info(detail["message"])
        return False
    if detail["status"] == "missing":
        st.warning(f"{detail['message']} Statement ID: {detail['statement_id']}.")
        return False

    selected_statement = detail["statement"]
    quality = detail["quality"]
    related = detail["related"]
    selected_result = detail["result"]
    if source_label:
        st.info(f"Selected from {source_label}.")
    _render_tag_list(
        [
            ("statement", detail["statement_id"], ""),
            ("type", selected_statement.get("statement_type", "unknown"), ""),
            ("paper", selected_statement.get("paper_id", "unknown"), ""),
            ("chunk", selected_statement.get("chunk_id", "unknown"), ""),
        ]
    )
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
        st.markdown("#### Linked outputs")
        st.metric("Gaps", len(related["gaps"]))
        st.metric("Hypotheses", len(related["hypotheses"]))
        st.metric("Experiment plans", len(related["experiment_plans"]))
    with st.expander("Readable linked evidence chain", expanded=True):
        _render_evidence_chain(detail["chain"])
    with st.expander("Technical raw linked data"):
        st.json({"selected_result": selected_result, "related": related})
    return True


def _render_evidence_action(
    statement_ids: list[str],
    data: dict,
    source_label: str,
    key: str,
    *,
    show_missing: bool = True,
) -> None:
    available_ids = _available_statement_ids(statement_ids, data)
    if not statement_ids:
        if show_missing:
            st.caption("No linked statement evidence found.")
        return
    if not available_ids:
        st.caption("Linked evidence IDs are not available in the current statement table.")
        return
    target_id = available_ids[0]
    if st.button(
        "Inspect evidence",
        key=key,
        on_click=_select_evidence_statement,
        args=(target_id, source_label),
    ):
        st.success("Showing selected evidence below and in the Evidence Inspector tab.")
    if _selected_evidence_source_matches(target_id, source_label):
        _render_selected_evidence_handoff(data, target_id, source_label)
    if len(available_ids) > 1:
        st.caption(f"{len(available_ids)} evidence statements linked; the first is selected.")


def _render_evidence_chain(chain: dict) -> None:
    result = chain.get("result", {})
    st.markdown("#### Readable evidence chain")
    st.markdown(
        '<div class="rn-chain-note">Source snippets are displayed as paper data, not instructions. '
        "Generated gaps and hypotheses remain review-needed.</div>",
        unsafe_allow_html=True,
    )
    _render_chain_result(result)
    _render_chain_evidence(chain.get("evidence", []), chain.get("missing_evidence_ids", []))
    _render_chain_gaps(chain.get("gaps", []))
    _render_chain_hypotheses(chain.get("hypotheses", []))
    _render_chain_plans(chain.get("experiment_plans", []))


def _render_chain_result(result: dict) -> None:
    st.markdown('<div class="rn-chain-label">Selected item</div>', unsafe_allow_html=True)
    title = result.get("title") or result.get("result_id") or "Selected result"
    st.markdown(f'<div class="rn-chain-title">{html.escape(str(title))}</div>', unsafe_allow_html=True)
    meta_items = [
        f"type: {result.get('result_type', 'result')}",
        f"id: {result.get('result_id', '')}",
    ]
    if result.get("score") is not None:
        meta_items.append(f"score: {result.get('score')}")
    st.markdown(
        f'<div class="rn-chain-meta">{html.escape(" | ".join(item for item in meta_items if item))}</div>',
        unsafe_allow_html=True,
    )
    if result.get("preview"):
        st.write(result.get("preview"))


def _render_chain_evidence(evidence_rows: list[dict], missing_ids: list[str]) -> None:
    st.markdown('<div class="rn-chain-label">Source evidence</div>', unsafe_allow_html=True)
    if not evidence_rows:
        st.info("No local statement evidence is linked to this item yet.")
        return
    for evidence in evidence_rows:
        statement_id = str(evidence.get("statement_id", ""))
        if evidence.get("status") == "missing":
            st.warning(f"Linked evidence ID `{statement_id}` was not found in the current statement table.")
            continue
        paper_id = evidence.get("paper_id") or "unknown paper"
        paper_title = evidence.get("paper_title") or paper_id
        statement_type = evidence.get("statement_type") or "statement"
        st.markdown(
            f'<div class="rn-chain-title">{html.escape(str(statement_type).replace("_", " ").title())}'
            f" from {html.escape(str(paper_id))}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="rn-chain-meta">statement id: {html.escape(statement_id)} | '
            f"paper: {html.escape(str(paper_title))}</div>",
            unsafe_allow_html=True,
        )
        st.write(evidence.get("statement_text") or "No statement snippet available.")
        if evidence.get("evidence_text") and evidence.get("evidence_text") != evidence.get("statement_text"):
            st.caption("Evidence snippet")
            st.write(evidence.get("evidence_text"))
    if missing_ids:
        st.caption(f"Missing linked evidence IDs: {', '.join(str(item) for item in missing_ids)}")


def _render_chain_gaps(gaps: list[dict]) -> None:
    st.markdown('<div class="rn-chain-label">Generated gaps</div>', unsafe_allow_html=True)
    if not gaps:
        st.info("No generated gaps are linked to this item.")
        return
    for gap in gaps:
        st.markdown(
            f'<div class="rn-chain-title">{html.escape(str(gap.get("gap_id", "gap")))}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="rn-chain-meta">type: {html.escape(str(gap.get("gap_type", "unknown")))} | '
            f'evidence ids: {html.escape(", ".join(gap.get("source_statement_ids", [])) or "none")}</div>',
            unsafe_allow_html=True,
        )
        st.write(gap.get("gap_text") or "No gap summary available.")


def _render_chain_hypotheses(hypotheses: list[dict]) -> None:
    st.markdown('<div class="rn-chain-label">Speculative hypotheses</div>', unsafe_allow_html=True)
    if not hypotheses:
        st.info("No generated hypotheses are linked to this item.")
        return
    for hypothesis in hypotheses:
        st.markdown(
            f'<div class="rn-chain-title">{html.escape(str(hypothesis.get("hypothesis_id", "hypothesis")))}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="rn-chain-meta">gap: {html.escape(str(hypothesis.get("gap_id", "")))} | '
            f'confidence: {html.escape(str(hypothesis.get("confidence_level", "unknown")))} | '
            f'safety: {html.escape(str(hypothesis.get("safety_label", "")))}</div>',
            unsafe_allow_html=True,
        )
        st.write(hypothesis.get("hypothesis_text") or "No hypothesis summary available.")


def _render_chain_plans(plans: list[dict]) -> None:
    st.markdown('<div class="rn-chain-label">Experiment plans</div>', unsafe_allow_html=True)
    if not plans:
        st.info("No experiment plan is linked to this item yet.")
        return
    for plan in plans:
        st.markdown(
            f'<div class="rn-chain-title">Plan for {html.escape(str(plan.get("hypothesis_id", "hypothesis")))}</div>',
            unsafe_allow_html=True,
        )
        for label, field in [
            ("Objective", "objective"),
            ("Method", "method"),
            ("Baseline/control", "baseline_or_control"),
            ("Metrics", "metrics"),
            ("Required data", "required_data"),
            ("Expected outcome", "expected_outcome"),
            ("Risks and limitations", "risks_and_limitations"),
        ]:
            value = plan.get(field)
            if value:
                st.markdown(f"**{label}:**")
                st.write(value)


def _render_corpus_setup() -> None:
    _section_header(
        "Local PDF corpus setup",
        "Add 5-10 permitted PDFs to the local workspace before running the deterministic pipeline.",
        "Corpus",
    )
    status = describe_pdf_corpus(DEFAULT_PAPERS_DIR, DEFAULT_MANIFEST_PATH)
    _metric_cards(
        [
            ("Local PDFs", status["pdf_count"]),
            ("Manifest entries", status["manifest_count"]),
            ("MVP range", f"{CORPUS_MIN_PDFS}-{CORPUS_MAX_PDFS}"),
            ("Processed DB", "ready" if DEFAULT_DB_PATH.exists() else "missing"),
        ],
        columns=4,
    )
    _render_corpus_status_message(status)

    with st.container(border=True):
        st.markdown("#### Add PDFs")
        uploaded_files = st.file_uploader(
            "PDF files",
            type=["pdf"],
            accept_multiple_files=True,
            help="Files are saved only under data/papers in this workspace.",
        )
        replace_existing = st.checkbox(
            "Replace existing local PDFs before saving",
            value=False,
            help="Only PDF files in data/papers are removed; processed artifacts are left untouched.",
        )
        confirmed_permission = st.checkbox(
            "I confirm these papers are synthetic, sample, open-access, or otherwise permitted.",
            value=False,
        )
        uploaded_names = [str(file.name) for file in uploaded_files]
        validation = validate_pdf_upload_selection(
            uploaded_names,
            existing_filenames=status["pdf_files"],
            replace_existing=replace_existing,
        )
        if uploaded_files:
            for warning in validation.warnings:
                st.warning(warning)
            for error in validation.errors:
                st.error(error)
        save_disabled = not uploaded_files or not confirmed_permission or bool(validation.errors)
        if st.button("Save PDFs locally", type="primary", disabled=save_disabled):
            try:
                result = save_uploaded_pdfs(
                    uploaded_files,
                    papers_dir=DEFAULT_PAPERS_DIR,
                    manifest_path=DEFAULT_MANIFEST_PATH,
                    confirmed_permission=confirmed_permission,
                    replace_existing=replace_existing,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                saved_count = len(result["saved_files"])
                status = result["corpus"]
                st.success(f"Saved {saved_count} PDF file{'s' if saved_count != 1 else ''} locally.")
                _render_dataframe(pd.DataFrame(result["saved_files"]))

    st.markdown("#### Local corpus files")
    pdf_rows = pd.DataFrame({"pdf_file": status["pdf_files"]})
    if pdf_rows.empty:
        st.info("No local PDFs found in data/papers yet.")
    else:
        _render_dataframe(pdf_rows)
    if status["missing_from_manifest"] or status["missing_from_disk"]:
        st.warning("The local manifest does not match the PDF files on disk.")
        _render_dataframe(
            pd.DataFrame(
                {
                    "missing_from_manifest": [", ".join(status["missing_from_manifest"]) or "none"],
                    "missing_from_disk": [", ".join(status["missing_from_disk"]) or "none"],
                }
            )
        )

    _render_pipeline_run_control("corpus")
    st.markdown("#### Terminal fallback")
    st.code("\n".join(PIPELINE_COMMANDS[:-1]), language="bash")
    if not DEFAULT_DB_PATH.exists():
        st.info(
            "Processed artifacts are missing. Use the Run local pipeline button or run the "
            "local commands above after saving the corpus."
        )


def _render_corpus_status_message(status: dict) -> None:
    if status["status"] == "ready":
        st.success("Local corpus is in the MVP range and the manifest matches the PDF files.")
    elif status["status"] == "empty":
        st.info("No local PDFs found yet. Add permitted papers to start the MVP corpus.")
    elif status["status"] == "below_minimum":
        remaining = CORPUS_MIN_PDFS - int(status["pdf_count"])
        st.warning(f"Found {status['pdf_count']} PDFs. Add at least {remaining} more before a full MVP run.")
    elif status["status"] == "over_limit":
        st.error(
            f"Found {status['pdf_count']} PDFs. The local MVP limit is {CORPUS_MAX_PDFS} PDFs."
        )
    elif status["status"] == "manifest_mismatch":
        st.warning("Manifest review needed before the final submission check.")


def _result_card(result: dict, data: dict, card_index: int = 0) -> None:
    related = get_related_items(
        result,
        data.get("gaps", []),
        data.get("hypotheses", []),
        data.get("experiment_plans", []),
    )
    result_title = _result_card_title(result)
    preview = _result_card_preview(result, result_title)
    evidence_statement_ids = _evidence_statement_ids_for_result(result, data)
    with st.container(border=True):
        st.markdown(
            f'<div class="rn-mini-label">{html.escape(str(result.get("result_type", "")).replace("_", " ").title())}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="rn-card-title">{html.escape(result_title)}</div>',
            unsafe_allow_html=True,
        )
        if preview:
            st.markdown(
                f'<div class="rn-card-preview">{html.escape(preview)}</div>',
                unsafe_allow_html=True,
            )
        _render_tag_list(_result_metadata_tags(result, data, evidence_statement_ids))
        result_type = result.get("result_type", "result")
        result_id = result.get("result_id", "")
        _render_evidence_action(
            evidence_statement_ids,
            data,
            f"{result_type}: {result_title}",
            f"inspect-search-{card_index}-{result_type}-{result_id}",
            show_missing=result.get("result_type") != "paper",
        )
        chain = build_evidence_chain(result, data)
        with st.expander("Open evidence chain"):
            _render_evidence_chain(chain)
        with st.expander("Technical raw payload"):
            st.json(
                {
                    "result": result,
                    "evidence_chain": chain,
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


def _triage_values(records: list[dict], field: str) -> list[str]:
    values: set[str] = set()
    for record in records:
        value = record.get(field)
        if isinstance(value, list):
            values.update(str(item) for item in value if str(item))
        elif value:
            values.add(str(value))
    return sorted(values)


def _triage_query_matches(record: dict, query: str, fields: list[str]) -> bool:
    normalized = query.strip().lower()
    if not normalized:
        return True
    haystack = []
    for field in fields:
        value = record.get(field, "")
        if isinstance(value, list):
            haystack.extend(str(item) for item in value)
        else:
            haystack.append(str(value))
    return normalized in " ".join(haystack).lower()


def _filter_gap_triage(
    gaps: list[dict],
    query: str,
    gap_type: str,
    evidence_type: str,
    evidence_status: str,
    min_evidence: int,
    min_papers: int,
) -> list[dict]:
    filtered = []
    for gap in gaps:
        if not _triage_query_matches(gap, query, ["gap_id", "gap_text", "display_label", "paper_ids"]):
            continue
        if gap_type != "all" and str(gap.get("gap_type", "")) != gap_type:
            continue
        if evidence_type != "all" and evidence_type not in gap.get("source_statement_types", []):
            continue
        if evidence_status != "all" and str(gap.get("evidence_status", "")) != evidence_status:
            continue
        if int(gap.get("evidence_count", 0)) < min_evidence:
            continue
        if int(gap.get("paper_count", 0)) < min_papers:
            continue
        filtered.append(gap)
    return filtered


def _sort_gap_triage(gaps: list[dict], sort_by: str) -> list[dict]:
    if sort_by == "Evidence count":
        return sorted(
            gaps,
            key=lambda item: (
                -int(item.get("evidence_count", 0)),
                -int(item.get("paper_count", 0)),
                str(item.get("gap_id", "")),
            ),
        )
    if sort_by == "Paper coverage":
        return sorted(
            gaps,
            key=lambda item: (
                -int(item.get("paper_count", 0)),
                -int(item.get("evidence_count", 0)),
                str(item.get("gap_id", "")),
            ),
        )
    if sort_by == "Gap type":
        return sorted(gaps, key=lambda item: (str(item.get("gap_type", "")), str(item.get("gap_id", ""))))
    return sorted(gaps, key=lambda item: (-int(item.get("rank_score", 0)), str(item.get("gap_id", ""))))


def _filter_hypothesis_triage(
    hypotheses: list[dict],
    query: str,
    confidence: str,
    safety_label: str,
    gap_type: str,
    plan_status: str,
    min_evidence: int,
    min_papers: int,
) -> list[dict]:
    filtered = []
    for hypothesis in hypotheses:
        if not _triage_query_matches(
            hypothesis,
            query,
            ["hypothesis_id", "hypothesis_text", "display_label", "gap_id", "linked_gap_label"],
        ):
            continue
        if confidence != "all" and str(hypothesis.get("confidence_level", "")) != confidence:
            continue
        if safety_label != "all" and str(hypothesis.get("safety_label", "")) != safety_label:
            continue
        if gap_type != "all" and str(hypothesis.get("linked_gap_type", "")) != gap_type:
            continue
        if plan_status == "with plan" and not hypothesis.get("experiment_plan_available"):
            continue
        if plan_status == "missing plan" and hypothesis.get("experiment_plan_available"):
            continue
        if int(hypothesis.get("evidence_count", 0)) < min_evidence:
            continue
        if int(hypothesis.get("paper_count", 0)) < min_papers:
            continue
        filtered.append(hypothesis)
    return filtered


def _sort_hypothesis_triage(hypotheses: list[dict], sort_by: str) -> list[dict]:
    confidence_order = {"high": 3, "medium": 2, "low": 1}
    if sort_by == "Evidence count":
        return sorted(
            hypotheses,
            key=lambda item: (
                -int(item.get("evidence_count", 0)),
                -int(item.get("paper_count", 0)),
                str(item.get("hypothesis_id", "")),
            ),
        )
    if sort_by == "Paper coverage":
        return sorted(
            hypotheses,
            key=lambda item: (
                -int(item.get("paper_count", 0)),
                -int(item.get("evidence_count", 0)),
                str(item.get("hypothesis_id", "")),
            ),
        )
    if sort_by == "Confidence":
        return sorted(
            hypotheses,
            key=lambda item: (
                -confidence_order.get(str(item.get("confidence_level", "")).lower(), 0),
                -int(item.get("evidence_count", 0)),
                str(item.get("hypothesis_id", "")),
            ),
        )
    if sort_by == "Experiment plan":
        return sorted(
            hypotheses,
            key=lambda item: (
                not bool(item.get("experiment_plan_available")),
                str(item.get("hypothesis_id", "")),
            ),
        )
    return sorted(
        hypotheses,
        key=lambda item: (-int(item.get("triage_score", 0)), str(item.get("hypothesis_id", ""))),
    )


def _tag_value(value: object, *, preserve_underscores: bool = False) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "none"
    if value is None or value == "":
        return "none"
    if preserve_underscores:
        return str(value)
    return str(value).replace("_", " ")


def _render_tag_list(tags: list[tuple[str, object, str]]) -> None:
    html_tags = []
    for label, value, tone in tags:
        if value is None or value == "" or value == []:
            continue
        preserve_underscores = label in {"id", "linked", "paper", "safety", "status"}
        html_tags.append(
            f'<span class="rn-tag {html.escape(tone)}">'
            f"{html.escape(label)}: {html.escape(_tag_value(value, preserve_underscores=preserve_underscores))}</span>"
        )
    if html_tags:
        st.markdown(f'<div class="rn-tag-list">{"".join(html_tags)}</div>', unsafe_allow_html=True)


def _render_evidence_warning(record: dict, item_name: str) -> None:
    status = str(record.get("evidence_status", ""))
    if status == "evidence-linked":
        return
    if status == "partial evidence":
        st.warning(f"Some linked evidence IDs for this {item_name} are missing from the current statement table.")
    elif status == "evidence IDs unavailable":
        st.warning(f"Linked evidence IDs for this {item_name} are not available in the current statement table.")
    else:
        st.warning(f"This {item_name} does not list local statement evidence.")


def _gap_next_action(gap: dict) -> tuple[str, str]:
    evidence_status = str(gap.get("evidence_status", ""))
    if evidence_status and evidence_status != "evidence-linked":
        return "Resolve evidence links", "warn"
    if int(gap.get("evidence_count", 0)) <= 1:
        return "Inspect source evidence", "action"
    if int(gap.get("paper_count", 0)) <= 1:
        return "Check paper coverage", "action"
    return "Compare linked hypotheses", "good"


def _hypothesis_next_action(hypothesis: dict) -> tuple[str, str]:
    if int(hypothesis.get("evidence_count", 0)) <= 0:
        return "Resolve evidence links", "warn"
    if not hypothesis.get("experiment_plan_available"):
        return "Draft experiment plan", "warn"
    if str(hypothesis.get("confidence_level", "")).lower() == "low":
        return "Inspect source evidence", "action"
    return "Review experiment plan", "good"


def _plan_for_hypothesis(hypothesis_id: str, plans: list[dict]) -> dict | None:
    for plan in plans:
        if str(plan.get("hypothesis_id", "")) == hypothesis_id:
            return plan.get("plan", {})
    return None


def _render_discoveries_tab(data: dict, counts: dict) -> None:
    _metric_cards(
        [
            ("Papers", counts["papers"]),
            ("Statements", counts["statements"]),
            ("Gaps", counts["gaps"]),
            ("Hypotheses", counts["hypotheses"]),
        ],
        columns=4,
    )
    st.markdown(
        """
        <div class="rn-callout">
          <strong>Rank score guide</strong><br>
          Gap score weights local evidence statements, paper coverage, result-with-limitation gaps,
          and limitation or future-work evidence. It orders review priority; it is not a claim of
          scientific certainty.
        </div>
        """,
        unsafe_allow_html=True,
    )

    ranked_gaps = rank_gaps(data["gaps"], data["statements"])
    triaged_hypotheses = prepare_hypothesis_triage(
        data["hypotheses"],
        data["gaps"],
        data["statements"],
        data["experiment_plans"],
    )

    _section_header("Gap triage", "Filter and sort evidence-backed candidate gaps before inspecting evidence.", "Discovery")
    if not ranked_gaps:
        st.info("No research gaps are available yet. Run the local discovery pipeline after extracting statements.")
    else:
        gap_control_cols = st.columns([2, 1, 1, 1])
        gap_query = gap_control_cols[0].text_input("Search gaps", key="gap-triage-query")
        gap_type = gap_control_cols[1].selectbox("Gap type", ["all"] + _triage_values(ranked_gaps, "gap_type"))
        evidence_type = gap_control_cols[2].selectbox(
            "Evidence type",
            ["all"] + _triage_values(ranked_gaps, "source_statement_types"),
        )
        gap_sort = gap_control_cols[3].selectbox(
            "Sort gaps by",
            ["Rank score", "Evidence count", "Paper coverage", "Gap type"],
        )
        gap_threshold_cols = st.columns(3)
        max_gap_evidence = max(int(gap.get("evidence_count", 0)) for gap in ranked_gaps)
        max_gap_papers = max(int(gap.get("paper_count", 0)) for gap in ranked_gaps)
        min_gap_evidence = gap_threshold_cols[0].selectbox("Min gap evidence", list(range(max_gap_evidence + 1)))
        min_gap_papers = gap_threshold_cols[1].selectbox("Min gap papers", list(range(max_gap_papers + 1)))
        gap_status = gap_threshold_cols[2].selectbox(
            "Evidence status",
            ["all"] + _triage_values(ranked_gaps, "evidence_status"),
        )
        filtered_gaps = _sort_gap_triage(
            _filter_gap_triage(
                ranked_gaps,
                gap_query,
                gap_type,
                evidence_type,
                gap_status,
                int(min_gap_evidence),
                int(min_gap_papers),
            ),
            gap_sort,
        )
        st.caption(f"Showing {len(filtered_gaps)} of {len(ranked_gaps)} gaps.")
        if not filtered_gaps:
            st.info("No gaps match the current triage filters. Try broadening the search or lowering thresholds.")
        for gap in filtered_gaps:
            next_action, next_action_tone = _gap_next_action(gap)
            gap_title = discovery_label(
                str(gap.get("gap_text", "")),
                fallback=str(gap.get("display_label") or gap.get("gap_id") or "Research gap"),
                max_chars=132,
            )
            gap_body = _discovery_body_text(gap, "gap_text", "Research gap")
            with st.container(border=True):
                st.markdown(
                    '<div class="rn-mini-label">Research gap</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="rn-card-title">{html.escape(gap_title)}</div>',
                    unsafe_allow_html=True,
                )
                if gap_body and _normalize_card_text(gap_body).lower() != _normalize_card_text(gap_title).lower():
                    st.markdown(
                        f'<div class="rn-card-preview">{html.escape(gap_body)}</div>',
                        unsafe_allow_html=True,
                    )
                _render_tag_list(
                    [
                        ("id", gap.get("gap_id"), ""),
                        ("score", gap.get("rank_score"), ""),
                        ("type", gap.get("gap_type", "unknown"), ""),
                        ("evidence", gap.get("evidence_count", 0), "good"),
                        ("papers", gap.get("paper_count", 0), "good"),
                        ("status", gap.get("evidence_status", ""), "warn" if gap.get("evidence_status") != "evidence-linked" else "good"),
                        ("next", next_action, next_action_tone),
                    ]
                )
                st.caption(f"Score inputs: {gap.get('rank_score_explanation')}")
                _render_evidence_warning(gap, "gap")
                _render_evidence_action(
                    _unique_statement_ids(gap.get("source_statement_ids", [])),
                    data,
                    f"gap: {gap.get('gap_id', '')}",
                    f"inspect-gap-{gap.get('gap_id', '')}",
                )
                gap_result = {
                    "result_type": "gap",
                    "result_id": gap.get("gap_id", ""),
                    "linked_gap_id": gap.get("gap_id", ""),
                    "title": gap.get("display_label") or gap.get("gap_id", ""),
                    "matched_text": gap.get("gap_text", ""),
                    "evidence_statement_ids": gap.get("source_statement_ids", []),
                }
                evidence = evidence_for_statement_ids(gap.get("source_statement_ids", []), data["statements"])
                with st.expander("Evidence chain"):
                    _render_evidence_chain(build_evidence_chain(gap_result, data))
                with st.expander("Technical gap payload"):
                    st.json({"gap": gap, "evidence_rows": evidence})

    _section_header(
        "Hypothesis triage",
        "Compare speculative hypotheses by linked evidence, confidence, safety label, and plan readiness.",
        "Experiment design",
    )
    if not triaged_hypotheses:
        st.info("No hypotheses are available yet. Run discovery after grounded gaps are available.")
        return

    hyp_control_cols = st.columns([2, 1, 1, 1])
    hypothesis_query = hyp_control_cols[0].text_input("Search hypotheses", key="hypothesis-triage-query")
    confidence = hyp_control_cols[1].selectbox(
        "Confidence",
        ["all"] + _triage_values(triaged_hypotheses, "confidence_level"),
    )
    safety_label = hyp_control_cols[2].selectbox(
        "Safety label",
        ["all"] + _triage_values(triaged_hypotheses, "safety_label"),
    )
    hypothesis_sort = hyp_control_cols[3].selectbox(
        "Sort hypotheses by",
        ["Triage score", "Evidence count", "Paper coverage", "Confidence", "Experiment plan"],
    )
    hyp_threshold_cols = st.columns(3)
    max_hyp_evidence = max(int(item.get("evidence_count", 0)) for item in triaged_hypotheses)
    max_hyp_papers = max(int(item.get("paper_count", 0)) for item in triaged_hypotheses)
    min_hyp_evidence = hyp_threshold_cols[0].selectbox("Min hypothesis evidence", list(range(max_hyp_evidence + 1)))
    min_hyp_papers = hyp_threshold_cols[1].selectbox("Min hypothesis papers", list(range(max_hyp_papers + 1)))
    plan_status = hyp_threshold_cols[2].selectbox("Plan status", ["all", "with plan", "missing plan"])
    gap_type_for_hypotheses = st.selectbox(
        "Linked gap type",
        ["all"] + _triage_values(triaged_hypotheses, "linked_gap_type"),
    )
    filtered_hypotheses = _sort_hypothesis_triage(
        _filter_hypothesis_triage(
            triaged_hypotheses,
            hypothesis_query,
            confidence,
            safety_label,
            gap_type_for_hypotheses,
            plan_status,
            int(min_hyp_evidence),
            int(min_hyp_papers),
        ),
        hypothesis_sort,
    )
    st.caption(f"Showing {len(filtered_hypotheses)} of {len(triaged_hypotheses)} hypotheses.")
    if not filtered_hypotheses:
        st.info("No hypotheses match the current triage filters. Try broadening the search or lowering thresholds.")
    for hypothesis in filtered_hypotheses:
        next_action, next_action_tone = _hypothesis_next_action(hypothesis)
        hypothesis_id = str(hypothesis.get("hypothesis_id", ""))
        hypothesis_title = discovery_label(
            str(hypothesis.get("hypothesis_text", "")),
            fallback=str(hypothesis.get("display_label") or hypothesis_id or "Hypothesis"),
            max_chars=132,
        )
        hypothesis_body = _discovery_body_text(hypothesis, "hypothesis_text", "Speculative hypothesis")
        with st.container(border=True):
            st.markdown(
                '<div class="rn-mini-label">Speculative hypothesis</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="rn-card-title">{html.escape(hypothesis_title)}</div>',
                unsafe_allow_html=True,
            )
            if (
                hypothesis_body
                and _normalize_card_text(hypothesis_body).lower() != _normalize_card_text(hypothesis_title).lower()
            ):
                st.markdown(
                    f'<div class="rn-card-preview">{html.escape(hypothesis_body)}</div>',
                    unsafe_allow_html=True,
                )
            _render_tag_list(
                [
                    ("id", hypothesis_id, ""),
                    ("triage", hypothesis.get("triage_score"), ""),
                    ("confidence", hypothesis.get("confidence_level", "unknown"), ""),
                    ("safety", hypothesis.get("safety_label", ""), "warn"),
                    ("evidence", hypothesis.get("evidence_count", 0), "good"),
                    ("papers", hypothesis.get("paper_count", 0), "good"),
                    (
                        "plan",
                        "available" if hypothesis.get("experiment_plan_available") else "missing",
                        "good" if hypothesis.get("experiment_plan_available") else "warn",
                    ),
                    ("next", next_action, next_action_tone),
                ]
            )
            st.caption(
                f"Linked gap: {hypothesis.get('linked_gap_label', '')} "
                f"({hypothesis.get('gap_id')})"
            )
            st.caption(f"Score inputs: {hypothesis.get('triage_score_explanation')}")
            _render_evidence_warning(hypothesis, "hypothesis")
            _render_evidence_action(
                _unique_statement_ids(hypothesis.get("evidence_statement_ids", [])),
                data,
                f"hypothesis: {hypothesis_id}",
                f"inspect-hypothesis-{hypothesis_id}",
            )
            hypothesis_result = {
                "result_type": "hypothesis",
                "result_id": hypothesis_id,
                "hypothesis_id": hypothesis_id,
                "gap_id": hypothesis.get("gap_id", ""),
                "title": hypothesis.get("display_label") or hypothesis_id,
                "matched_text": hypothesis.get("hypothesis_text", ""),
                "evidence_statement_ids": hypothesis.get("evidence_statement_ids", []),
                "confidence_level": hypothesis.get("confidence_level", ""),
                "safety_label": hypothesis.get("safety_label", ""),
            }
            plan = _plan_for_hypothesis(hypothesis_id, data["experiment_plans"])
            with st.expander("Evidence chain and experiment plan"):
                _render_evidence_chain(build_evidence_chain(hypothesis_result, data))
            with st.expander("Technical hypothesis payload"):
                st.json({"hypothesis": hypothesis, "experiment_plan": plan or {}})


def _subgraph_for_results(graph: nx.DiGraph, results: list[dict], max_nodes: int = 50) -> nx.DiGraph:
    if max_nodes <= 0:
        return nx.DiGraph()
    seed_groups: list[list[str]] = []
    for result in results:
        candidate_nodes = _related_graph_nodes(result)
        for evidence_id in result.get("evidence_statement_ids", []) or []:
            candidate_nodes.append(f"statement:{evidence_id}")
            candidate_nodes.extend(_semantic_nodes_for_statement(graph, str(evidence_id)))
        seed_groups.append(_unique_existing_nodes(graph, candidate_nodes))
    seed_groups = [group for group in seed_groups if group]
    if not seed_groups:
        return build_small_subgraph(graph, max_nodes=max_nodes)
    selected_nodes = _select_edge_preserving_nodes(graph, seed_groups, max_nodes)
    return graph.subgraph(selected_nodes).copy()


def _unique_existing_nodes(graph: nx.DiGraph, node_ids: list[str]) -> list[str]:
    existing_nodes: list[str] = []
    seen: set[str] = set()
    for node_id in node_ids:
        if node_id in seen or node_id not in graph:
            continue
        seen.add(node_id)
        existing_nodes.append(node_id)
    return existing_nodes


def _semantic_nodes_for_statement(graph: nx.DiGraph, statement_id: str) -> list[str]:
    semantic_nodes = []
    for node_id, attrs in graph.nodes(data=True):
        if str(attrs.get("statement_id", "")) != statement_id:
            continue
        if str(attrs.get("node_type", "")) == "statement":
            continue
        semantic_nodes.append(str(node_id))
    return sorted(semantic_nodes, key=lambda node_id: _graph_node_sort_key(graph, node_id))


def _select_edge_preserving_nodes(
    graph: nx.DiGraph,
    seed_groups: list[list[str]],
    max_nodes: int,
) -> list[str]:
    selected_nodes: list[str] = []
    selected_lookup: set[str] = set()

    def add_node(node_id: str) -> bool:
        if node_id in selected_lookup:
            return True
        if len(selected_lookup) >= max_nodes:
            return False
        selected_lookup.add(node_id)
        selected_nodes.append(node_id)
        return True

    for seed_group in seed_groups:
        for seed_node in seed_group:
            add_node(seed_node)
        for edge in _incident_edges_for_nodes(graph, seed_group):
            source, target, _attrs = edge
            if not add_node(str(source)):
                break
            if not add_node(str(target)):
                break
        if len(selected_lookup) >= max_nodes:
            break
    return selected_nodes


def _incident_edges_for_nodes(graph: nx.DiGraph, node_ids: list[str]) -> list[tuple[str, str, dict]]:
    node_lookup = set(node_ids)
    edges = [
        (str(source), str(target), attrs)
        for source, target, attrs in graph.edges(data=True)
        if str(source) in node_lookup or str(target) in node_lookup
    ]
    return sorted(edges, key=_edge_sort_key)


def _sorted_graph_edges(graph: nx.DiGraph) -> list[tuple[str, str, dict]]:
    return sorted(
        ((str(source), str(target), attrs) for source, target, attrs in graph.edges(data=True)),
        key=_edge_sort_key,
    )


def _edge_sort_key(edge: tuple[str, str, dict]) -> tuple[int, str, str]:
    source, target, attrs = edge
    relation_priority = {
        "supports": 0,
        "limited_by": 1,
        "motivates": 2,
        "used_by": 3,
        "contains": 4,
    }
    return (relation_priority.get(str(attrs.get("relation", "")), 9), str(source), str(target))


def _graph_node_sort_key(graph: nx.DiGraph, node_id: str) -> tuple[str, str, str]:
    attrs = graph.nodes[node_id]
    return (
        str(attrs.get("paper_id", "")),
        str(attrs.get("node_type", "")),
        str(node_id),
    )


def _graph_node_type(node_attrs: dict) -> str:
    return str(node_attrs.get("node_type", "unknown") or "unknown")


def _graph_node_type_sort_key(node_type: str) -> tuple[int, str]:
    return (GRAPH_NODE_TYPE_ORDER.get(node_type, 99), node_type)


def _graph_available_node_types(graph: nx.DiGraph) -> list[str]:
    return sorted(
        {_graph_node_type(attrs) for _node_id, attrs in graph.nodes(data=True)},
        key=_graph_node_type_sort_key,
    )


def _graph_available_relation_types(graph: nx.DiGraph) -> list[str]:
    return sorted(
        {
            str(attrs.get("relation", "related") or "related")
            for _source, _target, attrs in graph.edges(data=True)
        }
    )


def _graph_node_type_label(node_type: str) -> str:
    return str(GRAPH_NODE_TYPE_STYLES.get(node_type, {}).get("label") or node_type.replace("_", " ").title())


def _graph_node_type_description(node_type: str) -> str:
    return str(GRAPH_NODE_TYPE_STYLES.get(node_type, {}).get("description") or "Graph node")


def _filter_graph_by_node_types(graph: nx.DiGraph, node_types: list[str]) -> nx.DiGraph:
    selected_types = set(node_types)
    if not selected_types:
        return nx.DiGraph()
    selected_nodes = [
        node_id
        for node_id, attrs in graph.nodes(data=True)
        if _graph_node_type(attrs) in selected_types
    ]
    return graph.subgraph(selected_nodes).copy()


def _filter_graph_by_relation_types(graph: nx.DiGraph, relation_types: list[str]) -> nx.DiGraph:
    selected_relations = set(relation_types)
    filtered = nx.DiGraph()
    filtered.add_nodes_from(graph.nodes(data=True))
    if not selected_relations:
        return filtered
    filtered.add_edges_from(
        (source, target, attrs)
        for source, target, attrs in graph.edges(data=True)
        if str(attrs.get("relation", "related") or "related") in selected_relations
    )
    return filtered


def _clip_graph_label(value: object, max_chars: int = 42) -> str:
    text = _normalize_card_text(value)
    if len(text) <= max_chars:
        return text
    clipped = text[: max_chars - 3].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0].rstrip()
    return f"{clipped}..."


def _graph_display_label(node_id: str, attrs: dict, max_chars: int = 42) -> str:
    node_type = _graph_node_type(attrs)
    if node_type == "paper":
        label = attrs.get("title") or attrs.get("paper_title") or attrs.get("paper_id") or node_id.split(":", 1)[-1]
    elif node_type == "gap":
        label = humanize_discovery_text(str(attrs.get("gap_text") or attrs.get("label") or ""), fallback="Research gap")
    elif node_type == "hypothesis":
        label = humanize_discovery_text(
            str(attrs.get("hypothesis_text") or attrs.get("label") or ""),
            fallback="Speculative hypothesis",
        )
    elif node_type == "statement":
        label = attrs.get("statement_text") or attrs.get("evidence_text") or "Evidence statement"
    else:
        label = attrs.get("statement_text") or attrs.get("evidence_text") or attrs.get("label") or node_id.split(":", 1)[-1]
    return _clip_graph_label(label, max_chars)


def _graph_should_show_label(node_type: str, label_mode: str) -> bool:
    if label_mode == "All labels":
        return True
    if label_mode == "No labels":
        return False
    return bool(GRAPH_NODE_TYPE_STYLES.get(node_type, {}).get("default_label", False))


def _graph_label_sort_key(graph: nx.DiGraph, node_id: str) -> tuple[int, str, str]:
    attrs = dict(graph.nodes[node_id])
    node_type = _graph_node_type(attrs)
    priority = {
        "paper": 0,
        "gap": 1,
        "hypothesis": 2,
        "limitation": 3,
        "result": 4,
        "future_work": 5,
        "method": 6,
        "dataset": 7,
    }.get(node_type, 9)
    return (priority, str(attrs.get("paper_id", "")), str(node_id))


def _graph_label_node_ids(graph: nx.DiGraph, label_mode: str, max_key_labels: int = 14) -> set[str]:
    if label_mode == "All labels":
        return {str(node_id) for node_id in graph.nodes()}
    if label_mode == "No labels":
        return set()
    candidates = [
        str(node_id)
        for node_id, attrs in graph.nodes(data=True)
        if _graph_should_show_label(_graph_node_type(attrs), label_mode)
    ]
    return set(sorted(candidates, key=lambda node_id: _graph_label_sort_key(graph, node_id))[:max_key_labels])


def _graph_node_text_label(
    node_id: str,
    attrs: dict,
    label_mode: str,
    labeled_node_ids: set[str] | None = None,
) -> str:
    node_type = _graph_node_type(attrs)
    if not _graph_should_show_label(node_type, label_mode):
        return ""
    if labeled_node_ids is not None and str(node_id) not in labeled_node_ids:
        return ""
    return _graph_display_label(node_id, attrs, max_chars=34)


def _graph_hover_text(node_id: str, attrs: dict) -> str:
    node_type = _graph_node_type(attrs)
    parts = [
        f"<b>{html.escape(_graph_display_label(node_id, attrs, max_chars=120))}</b>",
        f"Type: {html.escape(_graph_node_type_label(node_type))}",
        f"ID: {html.escape(str(node_id))}",
    ]
    if attrs.get("paper_id"):
        parts.append(f"Paper: {html.escape(str(attrs.get('paper_id')))}")
    if attrs.get("statement_id"):
        parts.append(f"Evidence ID: {html.escape(str(attrs.get('statement_id')))}")
    if attrs.get("statement_type") and node_type == "statement":
        parts.append(f"Statement type: {html.escape(str(attrs.get('statement_type')))}")
    return "<br>".join(parts)


def _graph_node_color(node_type: str) -> str:
    return str(GRAPH_NODE_TYPE_STYLES.get(node_type, {}).get("color", "#334155"))


def _graph_node_size(node_type: str) -> int:
    return int(GRAPH_NODE_TYPE_STYLES.get(node_type, {}).get("size", 9))


def _graph_relation_summary(graph: nx.DiGraph) -> str:
    summary = graph_summary(graph)
    relation_types = summary.get("relation_types", {})
    if not relation_types:
        return "No visible relationships"
    return " | ".join(f"{relation}: {count}" for relation, count in relation_types.items())


def _render_graph_summary(graph: nx.DiGraph, source_note: str) -> None:
    summary = graph_summary(graph)
    _metric_cards(
        [
            ("Visible nodes", summary["nodes"]),
            ("Visible edges", summary["edges"]),
            ("Node types", len(summary["node_types"])),
            ("Relation types", len(summary["relation_types"])),
        ],
        columns=4,
    )
    st.caption(f"{source_note} Relationships: {_graph_relation_summary(graph)}.")


def _render_graph_legend(graph: nx.DiGraph) -> None:
    type_counts = graph_summary(graph).get("node_types", {})
    if not type_counts:
        return
    legend_items = []
    for node_type in sorted(type_counts, key=_graph_node_type_sort_key):
        label = _graph_node_type_label(node_type)
        count = type_counts[node_type]
        description = _graph_node_type_description(node_type)
        color = _graph_node_color(node_type)
        legend_items.append(
            '<span class="rn-graph-legend-item" title="'
            + html.escape(description)
            + '">'
            + f'<span class="rn-graph-dot" style="background:{html.escape(color)}"></span>'
            + html.escape(f"{label}: {count}")
            + "</span>"
        )
    st.markdown(f'<div class="rn-graph-legend">{"".join(legend_items)}</div>', unsafe_allow_html=True)


def _render_graph(graph: nx.DiGraph, label_mode: str = "Key labels") -> None:
    nodes_df, edges_df = graph_to_tables(graph)
    if graph.number_of_nodes() == 0:
        st.info("No graph data available yet.")
        return
    if graph.number_of_edges() == 0:
        st.warning(
            "This graph sample has nodes but no visible relationships. Try a search result with "
            "linked evidence or rerun graph generation."
        )
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
        labeled_node_ids = _graph_label_node_ids(graph, label_mode)
        fig.add_trace(
            go.Scatter(
                x=edge_x,
                y=edge_y,
                mode="lines",
                line={"width": 1, "color": "#94a3b8"},
                hoverinfo="skip",
            )
        )
        for node_type in _graph_available_node_types(graph):
            nodes = [
                node_id
                for node_id, attrs in sorted(graph.nodes(data=True), key=lambda item: str(item[0]))
                if _graph_node_type(attrs) == node_type
            ]
            text_labels = [
                _graph_node_text_label(str(node_id), dict(graph.nodes[node_id]), label_mode, labeled_node_ids)
                for node_id in nodes
            ]
            mode = "markers+text" if any(text_labels) else "markers"
            fig.add_trace(
                go.Scatter(
                    x=[positions[node][0] for node in nodes],
                    y=[positions[node][1] for node in nodes],
                    mode=mode,
                    marker={
                        "size": _graph_node_size(node_type),
                        "color": _graph_node_color(node_type),
                        "line": {"width": 0.8, "color": "#ffffff"},
                    },
                    text=text_labels,
                    textposition="top center",
                    textfont={"size": 10, "color": "#111827"},
                    hovertext=[_graph_hover_text(str(node), dict(graph.nodes[node])) for node in nodes],
                    hoverinfo="text",
                    name=_graph_node_type_label(node_type),
                )
            )
        fig.update_layout(showlegend=False, margin={"l": 0, "r": 0, "t": 10, "b": 0}, height=520)
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        _render_plotly_chart(fig)
    except Exception:
        st.info("Interactive graph rendering is unavailable. Showing a local static preview.")
        _render_static_graph_svg(graph, label_mode=label_mode)
    with st.expander("Node and edge tables"):
        _render_dataframe(nodes_df)
        _render_dataframe(edges_df)


def _render_static_graph_svg(graph: nx.DiGraph, label_mode: str = "Key labels") -> None:
    if graph.number_of_nodes() == 0:
        return
    positions = nx.spring_layout(graph, seed=7)
    width = 920
    height = 520
    padding = 42
    points = list(positions.values())
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)

    def scale(value: float, low: float, high: float, output_low: float, output_high: float) -> float:
        if high == low:
            return (output_low + output_high) / 2
        return output_low + ((value - low) / (high - low)) * (output_high - output_low)

    scaled_positions = {
        node_id: (
            scale(position[0], min_x, max_x, padding, width - padding),
            scale(position[1], min_y, max_y, height - padding, padding),
        )
        for node_id, position in positions.items()
    }
    edge_markup = []
    for source, target, attrs in _sorted_graph_edges(graph):
        x1, y1 = scaled_positions[source]
        x2, y2 = scaled_positions[target]
        relation = html.escape(str(attrs.get("relation", "")))
        edge_markup.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}">'
            f"<title>{relation}</title></line>"
        )
    node_markup = []
    labeled_node_ids = _graph_label_node_ids(graph, label_mode)
    for node_id, attrs in sorted(graph.nodes(data=True), key=lambda item: str(item[0])):
        x, y = scaled_positions[str(node_id)]
        node_type = str(attrs.get("node_type", "unknown"))
        color = _graph_node_color(node_type)
        radius = max(5, min(9, _graph_node_size(node_type) / 1.5))
        label = html.escape(_graph_node_text_label(str(node_id), dict(attrs), label_mode, labeled_node_ids))
        if x > width * 0.72:
            text_x = x - radius - 5
            text_anchor = "end"
        else:
            text_x = x + radius + 5
            text_anchor = "start"
        text_markup = (
            f'<text x="{text_x:.1f}" y="{y + 4:.1f}" text-anchor="{text_anchor}">{label}</text>'
            if label
            else ""
        )
        node_markup.append(
            f'<g><circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}">'
            f"<title>{html.escape(_graph_display_label(str(node_id), dict(attrs), max_chars=120))} "
            f"({html.escape(str(node_id))})</title></circle>"
            f"{text_markup}</g>"
        )
    svg = (
        f'<svg class="rn-static-graph" viewBox="0 0 {width} {height}" '
        'role="img" aria-label="Static knowledge graph preview">'
        "<defs><style>"
        ".rn-static-graph{width:100%;height:auto;border:1px solid #d8dee8;border-radius:8px;"
        "background:#ffffff}.rn-static-graph line{stroke:#94a3b8;stroke-width:1.2;"
        "opacity:.72}.rn-static-graph text{font:11px sans-serif;fill:#334155}"
        "</style></defs>"
        f'{"".join(edge_markup)}{"".join(node_markup)}</svg>'
    )
    st.markdown(svg, unsafe_allow_html=True)


def _render_search_workspace(
    data: dict,
    evaluation: dict,
    default_search_query: str,
    max_search_results: int,
) -> None:
    _section_header(
        "Search the local research corpus",
        "Results are ranked across papers, statements, gaps, hypotheses, and experiment plans.",
        "Discovery",
    )
    if "search_query" not in st.session_state:
        st.session_state["search_query"] = default_search_query
    paper_options = ["all"] + sorted(
        str(item)
        for item in data["papers"].get("paper_id", pd.Series(dtype=str)).dropna().unique()
    )
    with st.form("search_controls"):
        search_cols = st.columns([5, 1])
        query = search_cols[0].text_input(
            "Research question or keyword",
            placeholder="Find research gaps related to evaluation of AI-generated hypotheses",
            key="search_query",
        )
        search_submitted = search_cols[1].form_submit_button("Search", type="primary")
        filter_cols = st.columns(4)
        statement_type = filter_cols[0].selectbox("Statement type", STATEMENT_TYPES)
        result_type = filter_cols[1].selectbox("Result type", RESULT_TYPES)
        safety_threshold = filter_cols[2].slider(
            "Global safety warning threshold",
            0.0,
            1.0,
            0.0,
            0.1,
            help=(
                "Compares against evaluation_report.safety_score; search results do not "
                "have per-result safety scores."
            ),
        )
        paper_id = filter_cols[3].selectbox("Paper", paper_options)

    safety_message = _global_safety_threshold_message(evaluation, safety_threshold)
    if safety_message:
        tone, message = safety_message
        if tone == "warning":
            st.warning(message)
        else:
            st.info(message)

    if search_submitted:
        results_by_type = search_all(
            query,
            data,
            {
                "statement_type": statement_type,
                "result_type": result_type,
                "paper_id": paper_id,
            },
        )
        all_results = _flatten_results(results_by_type, query)
        results, limit_message = _limit_search_results(all_results, max_search_results)
        st.session_state["last_search_query"] = query
        st.session_state["last_search_results"] = results
        st.session_state["last_search_limit_message"] = limit_message
        st.session_state[SEARCH_RESULTS_PAGE_KEY] = 1

    active_query = st.session_state.get("last_search_query", "")
    results = st.session_state.get("last_search_results", [])
    limit_message = st.session_state.get("last_search_limit_message")
    if str(active_query).strip():
        _discovery_summary(results)
        if limit_message:
            st.caption(limit_message)
        if not results:
            st.info("No local matches found. Try a broader keyword or run the processing pipeline.")
            return

        page_size_options = _search_page_size_options(min(max_search_results, len(results)))
        if st.session_state.get(SEARCH_RESULTS_PAGE_SIZE_KEY) not in page_size_options:
            st.session_state[SEARCH_RESULTS_PAGE_SIZE_KEY] = page_size_options[0]
        pager_cols = st.columns([1, 1, 2])
        page_size = pager_cols[0].selectbox(
            "Results per page",
            page_size_options,
            index=0,
            key=SEARCH_RESULTS_PAGE_SIZE_KEY,
        )
        _visible_results, current_page, page_count = _paginate_search_results(
            results,
            int(st.session_state.get(SEARCH_RESULTS_PAGE_KEY, 1)),
            int(page_size),
        )
        if st.session_state.get(SEARCH_RESULTS_PAGE_KEY) != current_page:
            st.session_state[SEARCH_RESULTS_PAGE_KEY] = current_page
        if page_count > 1:
            current_page = pager_cols[1].selectbox(
                "Result page",
                list(range(1, page_count + 1)),
                index=current_page - 1,
                key=SEARCH_RESULTS_PAGE_KEY,
                format_func=lambda page: f"Page {page} of {page_count}",
            )
        else:
            pager_cols[1].markdown("&nbsp;", unsafe_allow_html=True)
        visible_results, current_page, page_count = _paginate_search_results(
            results,
            int(current_page),
            int(page_size),
        )
        st.markdown(
            f'<div class="rn-result-pager-note">{html.escape(_search_page_note(len(visible_results), len(results), current_page, page_count))}</div>',
            unsafe_allow_html=True,
        )
        _render_search_review_strip(data, len(visible_results), len(results), current_page, page_count)
        start_index = (current_page - 1) * int(page_size)
        for result_index, result in enumerate(visible_results, start=start_index):
            _result_card(result, data, result_index)
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


def main() -> None:
    st.set_page_config(page_title="ResearchNavigator Agent", layout="wide")
    _inject_global_styles()
    ui_settings = _load_ui_settings()
    default_search_query = str(ui_settings["default_search_query"])
    max_search_results = int(ui_settings["max_search_results"])
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
    artifact_readiness = build_artifact_readiness(ARTIFACT_SPECS)

    _render_header(counts, evaluation)
    _render_artifact_readiness(artifact_readiness, include_details=False)

    if not DEFAULT_DB_PATH.exists():
        _show_pipeline_instructions()

    _render_search_workspace(data, evaluation, default_search_query, max_search_results)
    with st.expander("Project metrics and artifact details", expanded=False):
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
        st.markdown("#### Artifact readiness")
        _render_artifact_readiness_details(artifact_readiness)
    _render_evaluation_caveats(evaluation)

    (
        corpus_tab,
        evidence_tab,
        discoveries_tab,
        themes_tab,
        graph_tab,
        report_tab,
        safety_tab,
        pipeline_tab,
    ) = st.tabs(
        [
            "Corpus Setup",
            "Evidence Inspector",
            "Discoveries",
            "Research Themes",
            "Knowledge Graph",
            "Report",
            "Safety & Evaluation",
            "Pipeline Trace",
        ]
    )

    with corpus_tab:
        _render_corpus_setup()

    with evidence_tab:
        _section_header(
            "Evidence inspector",
            "Review source statements, compact evidence snippets, quality signals, and linked discoveries.",
            "Grounding",
        )
        statements = data["statements"]
        if statements.empty:
            st.info("No statements are available yet. Run ingestion with statement extraction first.")
        else:
            statement_records = sorted(
                _statement_records(statements),
                key=lambda item: str(item.get("statement_id", "")),
            )
            statement_ids = [str(item.get("statement_id", "")) for item in statement_records]
            statement_labels = {
                str(item.get("statement_id", "")): _statement_option_label(item)
                for item in statement_records
            }
            requested_statement_id = str(st.session_state.get(SELECTED_EVIDENCE_KEY, "") or "")
            if requested_statement_id and requested_statement_id not in statement_ids:
                st.warning("Selected evidence is not available in the current statement table.")
                requested_statement_id = ""
            selected_index = (
                statement_ids.index(requested_statement_id) if requested_statement_id else 0
            )
            selectbox_key = f"{EVIDENCE_SELECTBOX_KEY}-{requested_statement_id or 'default'}"
            selected_statement_id = st.selectbox(
                "Statement",
                statement_ids,
                index=selected_index,
                format_func=lambda item: statement_labels.get(str(item), str(item)),
                key=selectbox_key,
            )
            if selected_statement_id != requested_statement_id:
                st.session_state[SELECTED_EVIDENCE_SOURCE_KEY] = ""
            st.session_state[SELECTED_EVIDENCE_KEY] = selected_statement_id
            selected_source = str(st.session_state.get(SELECTED_EVIDENCE_SOURCE_KEY, "") or "")
            _render_selected_evidence_inspector(data, selected_statement_id, selected_source)

    with discoveries_tab:
        _render_artifact_guidance(artifact_readiness, "discoveries")
        _render_discoveries_tab(data, counts)

    with themes_tab:
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
            _render_dataframe(theme_df)
            selected_theme = st.selectbox("Explore theme", [item["theme"] for item in themes])
            theme = next(item for item in themes if item["theme"] == selected_theme)
            evidence = evidence_for_statement_ids(theme["representative_statement_ids"], data["statements"])
            st.markdown("#### Representative evidence")
            _render_dataframe(pd.DataFrame(evidence))

    with graph_tab:
        search_results = st.session_state.get("last_search_results", [])
        subgraph = _subgraph_for_results(graph, search_results) if search_results else build_small_subgraph(graph)
        graph_source_note = (
            "Showing the search-linked subgraph from the latest result set."
            if search_results
            else "Showing a deterministic overview subgraph."
        )
        _section_header(
            "Knowledge graph",
            "Search-linked graph sample when results are available; otherwise an overview subgraph.",
            "Graph",
        )
        _render_artifact_guidance(artifact_readiness, "graph")
        available_node_types = _graph_available_node_types(subgraph)
        control_cols = st.columns([2, 2, 1])
        selected_node_types = control_cols[0].multiselect(
            "Node types",
            available_node_types,
            default=available_node_types,
            format_func=_graph_node_type_label,
            help="Filters the visible preview only; raw graph artifacts remain unchanged.",
        )
        node_filtered_subgraph = _filter_graph_by_node_types(subgraph, selected_node_types)
        available_relation_types = _graph_available_relation_types(node_filtered_subgraph)
        selected_relation_types = control_cols[1].multiselect(
            "Relations",
            available_relation_types,
            default=available_relation_types,
            format_func=lambda relation: str(relation).replace("_", " ").title(),
            help="Filters visible edges while keeping the selected nodes in view.",
        )
        label_mode = control_cols[2].selectbox("Labels", GRAPH_LABEL_MODES)
        filtered_subgraph = _filter_graph_by_relation_types(node_filtered_subgraph, selected_relation_types)
        _render_graph_summary(filtered_subgraph, graph_source_note)
        _render_graph_legend(filtered_subgraph)
        with st.expander("Graph summary data", expanded=False):
            st.json(graph_summary(filtered_subgraph))
        _render_graph(filtered_subgraph, label_mode=label_mode)

    with report_tab:
        _section_header("Exportable research brief", "A local Markdown brief generated from current artifacts.", "Report")
        _render_artifact_guidance(artifact_readiness, "brief")
        brief = create_research_brief(data)
        st.download_button(
            "Download Markdown brief",
            data=brief,
            file_name="researchnavigator_brief.md",
            mime="text/markdown",
        )
        st.text_area("Markdown brief preview", value=brief, height=520, disabled=True)

    with safety_tab:
        _render_artifact_guidance(artifact_readiness, "evaluation")
        if not evaluation:
            status = evaluation_status_summary(evaluation)
            _section_header(
                f"Evaluation status: {status['headline']}",
                str(status["summary"]),
                "Evaluation",
            )
            st.info("No evaluation report found. Run the evaluation command in Pipeline Trace.")
        else:
            status = evaluation_status_summary(evaluation)
            failed_checks = evaluation.get("failed_checks", [])
            _section_header(
                f"Evaluation status: {status['headline']}",
                str(status["summary"]),
                "Evaluation",
            )
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
            warnings = _evaluation_warnings(evaluation)
            if warnings:
                st.warning(
                    "Review these caveats before treating generated gaps, hypotheses, or plans as reliable."
                )
                _render_dataframe(pd.DataFrame(warnings))
            with st.expander("Metric details"):
                st.json(evaluation.get("metric_details", {}))
            if failed_checks:
                st.error("Failed checks require review.")
                _render_dataframe(pd.DataFrame(failed_checks))
            else:
                st.success(
                    "No deterministic safety failures detected; generated hypotheses remain speculative."
                )

    with pipeline_tab:
        agent_story = describe_agent_capabilities()
        trajectory = planned_tool_trajectory()
        _section_header("ADK agent view", "Local Google ADK-facing wrapper over deterministic research tools.", "Agent")
        _metric_cards(
            [
                ("Agent", agent_story["agent_name"]),
                ("Framework", agent_story["agent_framework"]),
                ("Callable tools", agent_story["tool_count"]),
                ("Mode", agent_story["mode"]),
            ],
            columns=4,
        )
        st.caption(agent_story["orchestration_pattern"])
        with st.expander("Agent instruction and safety boundaries", expanded=True):
            st.write(agent_story["model_policy"])
            _render_dataframe(
                pd.DataFrame(
                    {
                        "course_concept": agent_story["course_concepts"],
                    }
                )
            )
            _render_dataframe(pd.DataFrame(agent_story["capstone_concept_proofs"]))
            _render_dataframe(pd.DataFrame(agent_story["orchestration_rationale"]))
            _render_dataframe(
                pd.DataFrame(
                    {
                        "safety_boundary": agent_story["safety_boundaries"],
                    }
                )
            )
            _render_dataframe(
                pd.DataFrame(
                    {
                        "human_review_gate": agent_story["human_review_gates"],
                    }
                )
            )
        _section_header("ADK-facing tool manifest", "Callable tools exposed through the local agent layer.", "Tools")
        _render_dataframe(pd.DataFrame(agent_story["tools"]))
        _section_header(
            "Planned tool trajectory",
            "Deterministic orchestration path for a research-discovery request.",
            "Trajectory",
        )
        _render_dataframe(pd.DataFrame(trajectory["steps"]))
        st.caption(trajectory["why_this_is_agentic"])
        _render_dataframe(pd.DataFrame({"policy_gate": trajectory["policy_gates"]}))
        st.caption("Final answer contract: " + " | ".join(trajectory["final_answer_contract"]))

        _section_header(
            "Deterministic trace artifact",
            "Exported JSON trajectory for the capstone video and reproducibility checks.",
            "Trace",
        )
        agent_trace = load_json_file(DEFAULT_AGENT_TRACE_PATH)
        if agent_trace:
            trace_steps = list(agent_trace.get("steps", []) or [])
            _metric_cards(
                [
                    ("Trace ID", agent_trace.get("trace_id", "n/a")),
                    ("Trace steps", len(trace_steps)),
                    ("Mode", agent_trace.get("mode", "n/a")),
                ],
                columns=3,
            )
            _render_dataframe(
                pd.DataFrame(
                    [
                        {
                            "order": step.get("order", ""),
                            "step_type": step.get("step_type", ""),
                            "tool_name": step.get("tool_name", ""),
                            "safety_gate": step.get("safety_gate", ""),
                            "output_summary": step.get("output_summary", ""),
                        }
                        for step in trace_steps
                    ]
                )
            )
        else:
            st.info("No deterministic trace artifact found yet. Run the local export command below.")
        st.code(AGENT_TRACE_COMMAND, language="bash")

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
        _render_dataframe(pd.DataFrame(mcp_manifest))
        st.code("uv run python -m scripts.run_mcp_server", language="bash")

        _section_header("Pipeline steps", "Backend processing stages and generated artifact status.", "Operations")
        status = build_ingestion_status(data)
        if not status.empty:
            _section_header("Paper ingestion status")
            _render_dataframe(status)
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
        _render_artifact_status_table(artifact_readiness)
        _render_artifact_recovery_panel(artifact_readiness)
        with st.expander("Raw file presence"):
            _render_dataframe(
                file_presence(
                    [
                        DEFAULT_DB_PATH,
                        DEFAULT_GRAPH_PATH,
                        DEFAULT_DISCOVERY_PATH,
                        DEFAULT_EVALUATION_PATH,
                        DEFAULT_BRIEF_PATH,
                        DEFAULT_AGENT_TRACE_PATH,
                    ]
                )
            )
        _render_pipeline_run_control("pipeline")
        with st.expander("Full local command reference", expanded=False):
            st.code(
                "\n".join([*PIPELINE_COMMANDS, BRIEF_ARTIFACT_COMMAND, AGENT_TRACE_COMMAND]),
                language="bash",
            )
        with st.expander("Raw backend tables"):
            _render_dataframe(data["papers"])
            _render_dataframe(data["statements"])


if __name__ == "__main__":
    main()
