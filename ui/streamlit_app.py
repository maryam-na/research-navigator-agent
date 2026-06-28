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
    build_ingestion_status,
    build_research_themes,
    create_research_brief,
    evidence_for_statement_ids,
    file_presence,
    get_related_items,
    graph_to_tables,
    load_graph,
    load_table,
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

DEFAULT_DB_PATH = Path("data/processed/papers.sqlite")
DEFAULT_GRAPH_PATH = Path("data/processed/research_graph.graphml")
DEFAULT_DISCOVERY_PATH = Path("data/processed/gaps_and_hypotheses.json")
DEFAULT_EVALUATION_PATH = Path("data/processed/evaluation_report.json")
STATEMENT_TYPES = ["all", "method", "result", "limitation", "future_work", "dataset", "background"]
RESULT_TYPES = ["all", "statements", "gaps", "hypotheses", "experiment_plans"]
SELECTED_EVIDENCE_KEY = "selected_evidence_statement_id"
SELECTED_EVIDENCE_SOURCE_KEY = "selected_evidence_source"
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
        .rn-review-banner {
            border: 1px solid #fde68a;
            border-left: 4px solid var(--rn-amber);
            border-radius: 8px;
            background: #fffbeb;
            padding: 13px 15px;
            margin: 4px 0 18px;
            color: #1f2937;
        }
        .rn-review-banner.fail {
            border-color: #fecaca;
            border-left-color: var(--rn-red);
            background: #fff7f7;
        }
        .rn-review-title {
            font-weight: 760;
            color: var(--rn-ink);
            margin-bottom: 4px;
        }
        .rn-review-text {
            color: #4b5563;
            font-size: 0.92rem;
            margin-bottom: 6px;
        }
        .rn-review-banner ul {
            margin: 6px 0 0 18px;
            padding: 0;
            color: #374151;
            font-size: 0.9rem;
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
    status = evaluation_status_summary(evaluation)
    safety = status["safety_label"]
    grounding = status["grounding_label"]
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
                <span class="rn-pill {status["tone"]}">{html.escape(status["pill_text"])}</span>
              </div>
            </div>
            <div class="rn-hero-score">
              <div class="rn-score-label">Evaluation</div>
              <div class="rn-score-value">{html.escape(status["headline"])}</div>
              <div class="rn-score-note">Safety {html.escape(safety)} | Grounding {html.escape(grounding)} | {counts.get("statements", 0)} statements</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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


def _select_evidence_statement(statement_id: str, source_label: str) -> None:
    st.session_state[SELECTED_EVIDENCE_KEY] = statement_id
    st.session_state[SELECTED_EVIDENCE_SOURCE_KEY] = source_label


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
    if st.button("Inspect evidence", key=key):
        _select_evidence_statement(target_id, source_label)
        st.success("Evidence selected. Open the Evidence Inspector tab to review it.")
    if len(available_ids) > 1:
        st.caption(f"{len(available_ids)} evidence statements linked; the first is selected.")


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

    st.markdown("#### Process locally")
    st.code("\n".join(PIPELINE_COMMANDS[:-1]), language="bash")
    if not DEFAULT_DB_PATH.exists():
        st.info("Processed artifacts are missing. Run the local commands above after saving the corpus.")


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
        result_type = result.get("result_type", "result")
        result_title = result.get("title", result.get("result_id", ""))
        result_id = result.get("result_id", "")
        _render_evidence_action(
            _evidence_statement_ids_for_result(result, data),
            data,
            f"{result_type}: {result_title}",
            f"inspect-search-{card_index}-{result_type}-{result_id}",
            show_missing=result.get("result_type") != "paper",
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


def _render_graph(graph: nx.DiGraph) -> None:
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
        _render_plotly_chart(fig)
    except Exception:
        st.info("Interactive graph rendering is unavailable. Showing a local static preview.")
        _render_static_graph_svg(graph)
    with st.expander("Node and edge tables"):
        _render_dataframe(nodes_df)
        _render_dataframe(edges_df)


def _render_static_graph_svg(graph: nx.DiGraph) -> None:
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
    for node_id, attrs in sorted(graph.nodes(data=True), key=lambda item: str(item[0])):
        x, y = scaled_positions[str(node_id)]
        label = html.escape(_short_graph_label(str(node_id)))
        node_type = str(attrs.get("node_type", "unknown"))
        color = _graph_node_color(node_type)
        node_markup.append(
            f'<g><circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{color}">'
            f"<title>{html.escape(str(node_id))}</title></circle>"
            f'<text x="{x + 10:.1f}" y="{y + 4:.1f}">{label}</text></g>'
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


def _short_graph_label(node_id: str, max_chars: int = 30) -> str:
    label = node_id.split(":", 1)[-1]
    if len(label) <= max_chars:
        return label
    return label[: max_chars - 3] + "..."


def _graph_node_color(node_type: str) -> str:
    return {
        "paper": "#1d4ed8",
        "statement": "#64748b",
        "method": "#0f766e",
        "result": "#7c3aed",
        "limitation": "#b91c1c",
        "future_work": "#b45309",
        "dataset": "#0369a1",
        "background": "#475569",
    }.get(node_type, "#334155")


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
    _render_evaluation_caveats(evaluation)

    if not DEFAULT_DB_PATH.exists():
        _show_pipeline_instructions()

    tabs = st.tabs(
        [
            "Corpus Setup",
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
        _render_corpus_setup()

    with tabs[1]:
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
            for result_index, result in enumerate(results[:30]):
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
        st.session_state["last_search_results"] = results

    with tabs[2]:
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
            selected_statement_id = st.selectbox(
                "Statement",
                statement_ids,
                index=selected_index,
                format_func=lambda item: statement_labels.get(str(item), str(item)),
            )
            st.session_state[SELECTED_EVIDENCE_KEY] = selected_statement_id
            selected_source = st.session_state.get(SELECTED_EVIDENCE_SOURCE_KEY)
            if selected_source and selected_statement_id == requested_statement_id:
                st.info(f"Selected from {selected_source}.")
            selected_statement = (
                statements[statements["statement_id"] == selected_statement_id].iloc[0].to_dict()
            )
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

    with tabs[3]:
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
                _render_evidence_action(
                    _unique_statement_ids(gap.get("source_statement_ids", [])),
                    data,
                    f"gap: {gap.get('gap_id', '')}",
                    f"inspect-gap-{gap.get('gap_id', '')}",
                )
                with st.expander("Inspect evidence"):
                    evidence = evidence_for_statement_ids(gap.get("source_statement_ids", []), data["statements"])
                    _render_dataframe(pd.DataFrame(evidence))
        _section_header("Hypotheses", "Candidate hypotheses remain speculative and linked to local evidence.", "Experiment design")
        for hypothesis in data["hypotheses"]:
            with st.container(border=True):
                st.markdown(f"**{hypothesis.get('hypothesis_id')}**")
                st.write(hypothesis.get("hypothesis_text"))
                st.caption(
                    f"Gap: {hypothesis.get('gap_id')} | Confidence: {hypothesis.get('confidence_level')} | Safety: {hypothesis.get('safety_label')}"
                )
                _render_evidence_action(
                    _unique_statement_ids(hypothesis.get("evidence_statement_ids", [])),
                    data,
                    f"hypothesis: {hypothesis.get('hypothesis_id', '')}",
                    f"inspect-hypothesis-{hypothesis.get('hypothesis_id', '')}",
                )
                with st.expander("Evidence and experiment plan"):
                    evidence = evidence_for_statement_ids(hypothesis.get("evidence_statement_ids", []), data["statements"])
                    _render_dataframe(pd.DataFrame(evidence))
                    plans = [
                        item
                        for item in data["experiment_plans"]
                        if item.get("hypothesis_id") == hypothesis.get("hypothesis_id")
                    ]
                    if plans:
                        st.json(plans[0].get("plan", {}))

    with tabs[4]:
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

    with tabs[5]:
        search_results = st.session_state.get("last_search_results", [])
        subgraph = _subgraph_for_results(graph, search_results) if search_results else build_small_subgraph(graph)
        _section_header(
            "Knowledge graph",
            "Search-linked graph sample when results are available; otherwise an overview subgraph.",
            "Graph",
        )
        st.json(graph_summary(subgraph))
        _render_graph(subgraph)

    with tabs[6]:
        _section_header("Exportable research brief", "A local Markdown brief generated from current artifacts.", "Report")
        brief = create_research_brief(data)
        st.download_button(
            "Download Markdown brief",
            data=brief,
            file_name="researchnavigator_brief.md",
            mime="text/markdown",
        )
        st.code(brief, language="markdown")

    with tabs[7]:
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

    with tabs[8]:
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
            _render_dataframe(
                pd.DataFrame(
                    {
                        "course_concept": agent_story["course_concepts"],
                    }
                )
            )
            _render_dataframe(
                pd.DataFrame(
                    {
                        "safety_boundary": agent_story["safety_boundaries"],
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
        _render_dataframe(
            file_presence([DEFAULT_DB_PATH, DEFAULT_GRAPH_PATH, DEFAULT_DISCOVERY_PATH, DEFAULT_EVALUATION_PATH])
        )
        st.markdown("### Commands")
        st.code("\n".join(PIPELINE_COMMANDS), language="bash")
        with st.expander("Raw backend tables"):
            _render_dataframe(data["papers"])
            _render_dataframe(data["statements"])


if __name__ == "__main__":
    main()
