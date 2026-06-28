"""Local data loading and deterministic search helpers for the Streamlit UI."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

STATEMENT_TYPE_PRIORITY = {
    "limitation": 7,
    "future_work": 6,
    "result": 5,
    "method": 4,
    "dataset": 3,
    "background": 2,
    "unknown": 1,
}

CONFIDENCE_PRIORITY = {
    "high": 3,
    "medium": 2,
    "low": 1,
    "unknown": 0,
    "": 0,
}

STOPWORDS = {
    "about",
    "after",
    "also",
    "analysis",
    "based",
    "because",
    "between",
    "could",
    "data",
    "from",
    "have",
    "into",
    "more",
    "paper",
    "research",
    "result",
    "show",
    "study",
    "that",
    "their",
    "these",
    "this",
    "through",
    "using",
    "with",
    "would",
}


def load_table(db_path: str | Path, table_name: str) -> pd.DataFrame:
    path = Path(db_path)
    allowed_tables = {"papers", "chunks", "statements"}
    if table_name not in allowed_tables:
        raise ValueError(f"Unsupported table: {table_name}")
    if not path.exists():
        return pd.DataFrame()
    with sqlite3.connect(path) as conn:
        return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)


def load_json_file(path: str | Path) -> dict[str, Any]:
    json_path = Path(path)
    if not json_path.exists():
        return {}
    return json.loads(json_path.read_text(encoding="utf-8"))


def load_graph(path: str | Path) -> nx.DiGraph:
    graph_path = Path(path)
    if not graph_path.exists():
        return nx.DiGraph()
    return nx.read_graphml(graph_path)


def graph_to_tables(graph: nx.DiGraph) -> tuple[pd.DataFrame, pd.DataFrame]:
    nodes = [
        {"node_id": node_id, **attrs}
        for node_id, attrs in sorted(graph.nodes(data=True), key=lambda item: str(item[0]))
    ]
    edges = [
        {"source": source, "target": target, **attrs}
        for source, target, attrs in sorted(
            graph.edges(data=True),
            key=lambda item: (str(item[0]), str(item[1]), str(item[2].get("relation", ""))),
        )
    ]
    return pd.DataFrame(nodes), pd.DataFrame(edges)


def statement_lookup(statements: pd.DataFrame | list[dict]) -> dict[str, dict]:
    """Return statements indexed by statement_id for evidence inspection."""

    return {
        str(row.get("statement_id", "")): row
        for row in _records(statements)
        if row.get("statement_id")
    }


def evidence_for_statement_ids(
    statement_ids: list[str],
    statements: pd.DataFrame | list[dict],
    max_chars: int = 220,
) -> list[dict]:
    """Return compact evidence snippets for a list of statement IDs."""

    lookup = statement_lookup(statements)
    evidence = []
    for statement_id in statement_ids:
        statement = lookup.get(str(statement_id))
        if not statement:
            continue
        evidence.append(
            {
                "statement_id": str(statement_id),
                "paper_id": statement.get("paper_id", ""),
                "statement_type": statement.get("statement_type", ""),
                "statement_text": _clip_text(str(statement.get("statement_text", "")), max_chars),
                "evidence_text": _clip_text(str(statement.get("evidence_text", "")), max_chars),
            }
        )
    return evidence


def score_statement_quality(statement: dict) -> dict:
    """Compute deterministic statement quality signals for UI inspection."""

    text = str(statement.get("statement_text", ""))
    evidence = str(statement.get("evidence_text", ""))
    statement_type = str(statement.get("statement_type", "unknown"))
    text_len = len(text.strip())
    has_evidence = bool(evidence.strip())
    useful_type = statement_type in {"method", "result", "limitation", "future_work", "dataset"}
    citation_risk = min(1.0, len(re.findall(r"\[[0-9,\s-]+\]|\([A-Z][A-Za-z]+ et al\.,? \d{4}\)", text)) / 3)
    number_risk = min(1.0, len(re.findall(r"\d", text)) / max(len(text), 1) * 4)
    length_score = 1.0 if 60 <= text_len <= 260 else 0.6 if 40 <= text_len <= 360 else 0.25
    grounding = 1.0 if has_evidence and text in evidence else 0.8 if has_evidence else 0.0
    usefulness = min(1.0, length_score + (0.2 if useful_type else 0.0))
    overall = max(0.0, min(1.0, (grounding * 0.45) + (usefulness * 0.45) - (citation_risk * 0.1)))
    return {
        "statement_id": statement.get("statement_id", ""),
        "grounding_confidence": round(grounding, 2),
        "usefulness_score": round(usefulness, 2),
        "citation_reference_risk": round(citation_risk, 2),
        "number_density_risk": round(number_risk, 2),
        "overall_quality": round(overall, 2),
    }


def rank_gaps(gaps: list[dict], statements: pd.DataFrame | list[dict]) -> list[dict]:
    """Rank gaps by evidence count, paper diversity, and actionability."""

    lookup = statement_lookup(statements)
    ranked = []
    for gap in gaps:
        source_ids = [str(item) for item in gap.get("source_statement_ids", [])]
        papers = {
            str(item)
            for item in gap.get("paper_ids", [])
            if str(item)
        }
        papers.update(str(lookup[item].get("paper_id", "")) for item in source_ids if item in lookup)
        papers = sorted(item for item in papers if item)
        source_types = sorted({str(lookup[item].get("statement_type", "")) for item in source_ids if item in lookup})
        available_evidence_count = sum(1 for item in source_ids if item in lookup)
        score_parts = {
            "evidence": len(source_ids) * 3,
            "paper_coverage": len(papers) * 2,
            "result_limitation_bonus": 2 if gap.get("gap_type") == "result_with_limitation" else 0,
            "future_work_bonus": 1 if "future_work" in source_types else 0,
            "limitation_bonus": 1 if "limitation" in source_types else 0,
        }
        score = sum(score_parts.values())
        ranked.append(
            {
                **gap,
                "display_label": discovery_label(str(gap.get("gap_text", "")), str(gap.get("gap_id", "Research gap"))),
                "rank_score": score,
                "rank_score_parts": score_parts,
                "rank_score_explanation": _rank_score_explanation(score_parts),
                "evidence_count": len(source_ids),
                "available_evidence_count": available_evidence_count,
                "paper_count": len(papers),
                "paper_ids": papers,
                "source_statement_types": source_types,
                "evidence_status": _evidence_status(len(source_ids), available_evidence_count),
            }
        )
    return sorted(
        ranked,
        key=lambda item: (-int(item.get("rank_score", 0)), str(item.get("gap_id", ""))),
    )


def prepare_hypothesis_triage(
    hypotheses: list[dict],
    gaps: list[dict],
    statements: pd.DataFrame | list[dict],
    experiment_plans: list[dict] | None = None,
) -> list[dict]:
    """Add deterministic triage metadata to hypotheses without changing generated text."""

    lookup = statement_lookup(statements)
    ranked_gaps = {str(item.get("gap_id", "")): item for item in rank_gaps(gaps, statements)}
    plan_ids = {str(plan.get("hypothesis_id", "")) for plan in experiment_plans or []}
    triaged = []
    for hypothesis in hypotheses:
        evidence_ids = [str(item) for item in hypothesis.get("evidence_statement_ids", [])]
        gap_id = str(hypothesis.get("gap_id", ""))
        linked_gap = ranked_gaps.get(gap_id, {})
        papers = {
            str(lookup[item].get("paper_id", ""))
            for item in evidence_ids
            if item in lookup
        }
        papers.update(str(item) for item in linked_gap.get("paper_ids", []) if str(item))
        papers = sorted(item for item in papers if item)
        available_evidence_count = sum(1 for item in evidence_ids if item in lookup)
        confidence = str(hypothesis.get("confidence_level", "")).lower()
        safety_label = str(hypothesis.get("safety_label", ""))
        score_parts = {
            "evidence": len(evidence_ids) * 3,
            "paper_coverage": len(papers) * 2,
            "confidence": CONFIDENCE_PRIORITY.get(confidence, 0) * 2,
            "safety_label": 2 if safety_label == "speculative_research_hypothesis" else 0,
            "experiment_plan": 1 if str(hypothesis.get("hypothesis_id", "")) in plan_ids else 0,
        }
        triaged.append(
            {
                **hypothesis,
                "display_label": discovery_label(
                    str(hypothesis.get("hypothesis_text", "")),
                    str(hypothesis.get("hypothesis_id", "Hypothesis")),
                ),
                "linked_gap_label": linked_gap.get("display_label", gap_id),
                "linked_gap_type": linked_gap.get("gap_type", ""),
                "triage_score": sum(score_parts.values()),
                "triage_score_parts": score_parts,
                "triage_score_explanation": _hypothesis_score_explanation(score_parts),
                "evidence_count": len(evidence_ids),
                "available_evidence_count": available_evidence_count,
                "paper_count": len(papers),
                "paper_ids": papers,
                "evidence_status": _evidence_status(len(evidence_ids), available_evidence_count),
                "experiment_plan_available": str(hypothesis.get("hypothesis_id", "")) in plan_ids,
            }
        )
    return sorted(
        triaged,
        key=lambda item: (-int(item.get("triage_score", 0)), str(item.get("hypothesis_id", ""))),
    )


def discovery_label(text: str, fallback: str = "Discovery", max_chars: int = 96) -> str:
    """Create a readable label from generated discovery text while keeping IDs secondary."""

    normalized = re.sub(r"\s+", " ", text).strip()
    prefixes = (
        "A possible research gap is suggested by a reported limitation:",
        "A possible research gap is suggested by reported future work:",
        "A possible research gap is suggested by:",
        "A testable hypothesis could be that",
    )
    for prefix in prefixes:
        if normalized.lower().startswith(prefix.lower()):
            normalized = normalized[len(prefix):].strip()
            break
    normalized = normalized[:1].upper() + normalized[1:] if normalized else str(fallback)
    return _clip_text(normalized, max_chars)


def build_research_themes(
    statements: pd.DataFrame | list[dict],
    graph: nx.DiGraph | None = None,
    max_themes: int = 8,
) -> list[dict]:
    """Create deterministic research themes from recurring keywords and graph presence."""

    theme_buckets: dict[str, dict] = {}
    for statement in _records(statements):
        text = str(statement.get("statement_text", ""))
        keywords = _keywords(text)
        if not keywords:
            continue
        theme_name = " / ".join(keywords[:2])
        bucket = theme_buckets.setdefault(
            theme_name,
            {
                "theme": theme_name,
                "keywords": keywords[:5],
                "statement_ids": [],
                "paper_ids": set(),
                "statement_types": set(),
            },
        )
        bucket["statement_ids"].append(str(statement.get("statement_id", "")))
        bucket["paper_ids"].add(str(statement.get("paper_id", "")))
        bucket["statement_types"].add(str(statement.get("statement_type", "")))

    themes = []
    for theme in theme_buckets.values():
        statement_ids = sorted(item for item in theme["statement_ids"] if item)
        graph_nodes = 0
        if graph is not None:
            graph_nodes = sum(1 for statement_id in statement_ids if f"statement:{statement_id}" in graph)
        themes.append(
            {
                "theme": theme["theme"],
                "keywords": theme["keywords"],
                "statement_count": len(statement_ids),
                "paper_count": len(theme["paper_ids"]),
                "statement_types": sorted(theme["statement_types"]),
                "representative_statement_ids": statement_ids[:5],
                "graph_nodes": graph_nodes,
            }
        )
    return sorted(
        themes,
        key=lambda item: (-int(item["statement_count"]), -int(item["paper_count"]), str(item["theme"])),
    )[:max_themes]


def build_ingestion_status(data: dict[str, Any]) -> pd.DataFrame:
    """Summarize pipeline completeness per paper for the dashboard."""

    papers = data.get("papers", pd.DataFrame())
    chunks = data.get("chunks", pd.DataFrame())
    statements = data.get("statements", pd.DataFrame())
    gaps = data.get("gaps", [])
    hypotheses = data.get("hypotheses", [])
    rows = []
    for paper in _records(papers):
        paper_id = str(paper.get("paper_id", ""))
        paper_chunks = chunks[chunks["paper_id"] == paper_id] if isinstance(chunks, pd.DataFrame) and "paper_id" in chunks else []
        paper_statements = (
            statements[statements["paper_id"] == paper_id]
            if isinstance(statements, pd.DataFrame) and "paper_id" in statements
            else []
        )
        statement_ids = set(
            str(row.get("statement_id", ""))
            for row in (_records(paper_statements) if not isinstance(paper_statements, list) else paper_statements)
        )
        gap_count = sum(
            1
            for gap in gaps
            if any(str(item) in statement_ids for item in gap.get("source_statement_ids", []))
        )
        hypothesis_count = sum(
            1
            for hypothesis in hypotheses
            if any(str(item) in statement_ids for item in hypothesis.get("evidence_statement_ids", []))
        )
        chunk_count = len(paper_chunks)
        statement_count = len(paper_statements)
        rows.append(
            {
                "paper_id": paper_id,
                "title": paper.get("title", paper_id),
                "extracted": chunk_count > 0,
                "chunk_count": chunk_count,
                "statement_count": statement_count,
                "gap_count": gap_count,
                "hypothesis_count": hypothesis_count,
                "status": _pipeline_status(chunk_count, statement_count, gap_count, hypothesis_count),
            }
        )
    return pd.DataFrame(rows)


def create_research_brief(data: dict[str, Any], max_items: int = 5) -> str:
    """Create a local Markdown research brief suitable for export."""

    ranked_gaps = rank_gaps(data.get("gaps", []), data.get("statements", pd.DataFrame()))[:max_items]
    hypotheses = sorted(data.get("hypotheses", []), key=lambda item: str(item.get("hypothesis_id", "")))[:max_items]
    themes = build_research_themes(data.get("statements", pd.DataFrame()), data.get("graph"), max_themes=max_items)
    lines = [
        "# ResearchNavigator Local Brief",
        "",
        "This report was generated locally from deterministic extraction, graph, safety, and evaluation outputs.",
        "",
        "## Top Research Themes",
    ]
    if themes:
        for theme in themes:
            lines.append(
                f"- **{theme['theme']}**: {theme['statement_count']} statements across {theme['paper_count']} papers."
            )
    else:
        lines.append("- No themes available yet.")
    lines.extend(["", "## Ranked Research Gaps"])
    if ranked_gaps:
        for gap in ranked_gaps:
            lines.append(
                f"- **{gap.get('gap_id')}** (score {gap.get('rank_score')}): {gap.get('gap_text')}"
            )
            lines.append(f"  Evidence IDs: {', '.join(gap.get('source_statement_ids', []))}")
    else:
        lines.append("- No gaps available yet.")
    lines.extend(["", "## Candidate Hypotheses"])
    if hypotheses:
        for hypothesis in hypotheses:
            lines.append(f"- **{hypothesis.get('hypothesis_id')}**: {hypothesis.get('hypothesis_text')}")
            lines.append(
                f"  Gap: {hypothesis.get('gap_id')} | Confidence: {hypothesis.get('confidence_level')} | Safety: {hypothesis.get('safety_label')}"
            )
    else:
        lines.append("- No hypotheses available yet.")
    return "\n".join(lines).strip() + "\n"


def file_presence(paths: list[str | Path]) -> pd.DataFrame:
    rows = []
    for path_value in paths:
        path = Path(path_value)
        rows.append(
            {
                "file": str(path),
                "present": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    return pd.DataFrame(rows)


def load_processed_data(
    db_path: str | Path,
    gaps_path: str | Path | None = None,
    evaluation_path: str | Path | None = None,
    graph_path: str | Path | None = None,
) -> dict[str, Any]:
    discovery = load_json_file(gaps_path) if gaps_path is not None else {}
    return {
        "papers": load_table(db_path, "papers"),
        "chunks": load_table(db_path, "chunks"),
        "statements": load_table(db_path, "statements"),
        "gaps": discovery.get("gaps", []),
        "hypotheses": discovery.get("hypotheses", []),
        "experiment_plans": discovery.get("experiment_plans", []),
        "evaluation": load_json_file(evaluation_path) if evaluation_path is not None else {},
        "graph": load_graph(graph_path) if graph_path is not None else nx.DiGraph(),
    }


def search_papers(query: str, papers: pd.DataFrame) -> list[dict]:
    if _empty_query(query) or papers.empty:
        return []
    results = []
    for row in papers.to_dict("records"):
        haystack = " ".join(str(row.get(field, "")) for field in ("title", "authors", "venue", "paper_id"))
        score = _match_score(query, haystack, result_type="paper")
        if score <= 0:
            continue
        results.append(
            {
                "result_type": "paper",
                "result_id": row.get("paper_id", ""),
                "title": row.get("title") or row.get("paper_id", "Paper"),
                "matched_text": haystack,
                "paper_id": row.get("paper_id", ""),
                "evidence_snippet": row.get("source_path", ""),
                "score": score,
            }
        )
    return rank_results(query, results)


def search_statements(query: str, statements: pd.DataFrame | list[dict], filters: dict | None = None) -> list[dict]:
    if _empty_query(query):
        return []
    records = _records(statements)
    filters = filters or {}
    statement_type = filters.get("statement_type")
    paper_id = filters.get("paper_id")
    results = []
    for row in records:
        if statement_type and statement_type != "all" and row.get("statement_type") != statement_type:
            continue
        if paper_id and paper_id != "all" and row.get("paper_id") != paper_id:
            continue
        haystack = " ".join(
            str(row.get(field, "")) for field in ("statement_text", "evidence_text", "paper_id", "chunk_id")
        )
        score = _match_score(
            query,
            haystack,
            result_type="statement",
            statement_type=str(row.get("statement_type", "unknown")),
            has_evidence=bool(row.get("evidence_text")),
        )
        if score <= 0:
            continue
        results.append(
            {
                "result_type": "statement",
                "result_id": row.get("statement_id", ""),
                "title": f"{row.get('statement_type', 'statement')}: {row.get('statement_id', '')}",
                "matched_text": row.get("statement_text", ""),
                "paper_id": row.get("paper_id", ""),
                "statement_id": row.get("statement_id", ""),
                "chunk_id": row.get("chunk_id", ""),
                "statement_type": row.get("statement_type", ""),
                "evidence_snippet": row.get("evidence_text", ""),
                "score": score,
            }
        )
    return rank_results(query, results)


def search_gaps(query: str, gaps: list[dict]) -> list[dict]:
    if _empty_query(query):
        return []
    results = []
    for gap in gaps:
        haystack = " ".join(
            [
                str(gap.get("gap_text", "")),
                " ".join(str(item) for item in gap.get("evidence_text", [])),
                " ".join(str(item) for item in gap.get("source_statement_ids", [])),
            ]
        )
        score = _match_score(query, haystack, result_type="gap", has_evidence=bool(gap.get("source_statement_ids")))
        if score <= 0:
            continue
        results.append(
            {
                "result_type": "gap",
                "result_id": gap.get("gap_id", ""),
                "title": gap.get("gap_id", "Research gap"),
                "matched_text": gap.get("gap_text", ""),
                "paper_id": ", ".join(str(item) for item in gap.get("paper_ids", [])),
                "evidence_statement_ids": gap.get("source_statement_ids", []),
                "evidence_snippet": " ".join(str(item) for item in gap.get("evidence_text", [])[:2]),
                "score": score,
            }
        )
    return rank_results(query, results)


def search_hypotheses(query: str, hypotheses: list[dict]) -> list[dict]:
    if _empty_query(query):
        return []
    results = []
    for hypothesis in hypotheses:
        haystack = " ".join(
            str(hypothesis.get(field, ""))
            for field in ("hypothesis_text", "rationale", "gap_id", "confidence_level", "safety_label")
        )
        score = _match_score(
            query,
            haystack,
            result_type="hypothesis",
            has_evidence=bool(hypothesis.get("evidence_statement_ids")),
        )
        if score <= 0:
            continue
        results.append(
            {
                "result_type": "hypothesis",
                "result_id": hypothesis.get("hypothesis_id", ""),
                "title": hypothesis.get("hypothesis_id", "Hypothesis"),
                "matched_text": hypothesis.get("hypothesis_text", ""),
                "linked_gap_id": hypothesis.get("gap_id", ""),
                "evidence_statement_ids": hypothesis.get("evidence_statement_ids", []),
                "safety_label": hypothesis.get("safety_label", ""),
                "confidence_level": hypothesis.get("confidence_level", ""),
                "score": score,
            }
        )
    return rank_results(query, results)


def search_experiment_plans(query: str, experiment_plans: list[dict]) -> list[dict]:
    if _empty_query(query):
        return []
    results = []
    for item in experiment_plans:
        plan = item.get("plan", {})
        haystack = _plan_text(plan)
        score = _match_score(query, haystack, result_type="experiment_plan")
        if score <= 0:
            continue
        results.append(
            {
                "result_type": "experiment_plan",
                "result_id": item.get("hypothesis_id", ""),
                "title": f"Experiment plan for {item.get('hypothesis_id', '')}",
                "matched_text": str(plan.get("objective", "")),
                "linked_hypothesis_id": item.get("hypothesis_id", ""),
                "experiment_plan": plan,
                "score": score,
            }
        )
    return rank_results(query, results)


def rank_results(query: str, results: list[dict]) -> list[dict]:
    query_text = query.lower().strip()
    return sorted(
        results,
        key=lambda item: (
            -float(item.get("score", _match_score(query_text, str(item)))),
            str(item.get("result_type", "")),
            str(item.get("result_id", "")),
        ),
    )


def get_related_items(
    result: dict,
    gaps: list[dict],
    hypotheses: list[dict],
    experiment_plans: list[dict],
) -> dict:
    statement_id = result.get("statement_id") or result.get("result_id")
    gap_id = result.get("linked_gap_id") or result.get("gap_id")
    hypothesis_id = result.get("linked_hypothesis_id") or result.get("hypothesis_id")

    related_gaps = [
        gap
        for gap in gaps
        if (statement_id and statement_id in gap.get("source_statement_ids", []))
        or (gap_id and gap.get("gap_id") == gap_id)
    ]
    related_hypotheses = [
        hypothesis
        for hypothesis in hypotheses
        if (statement_id and statement_id in hypothesis.get("evidence_statement_ids", []))
        or (gap_id and hypothesis.get("gap_id") == gap_id)
        or (hypothesis_id and hypothesis.get("hypothesis_id") == hypothesis_id)
    ]
    related_plans = [
        plan
        for plan in experiment_plans
        if any(plan.get("hypothesis_id") == hypothesis.get("hypothesis_id") for hypothesis in related_hypotheses)
        or (hypothesis_id and plan.get("hypothesis_id") == hypothesis_id)
    ]
    return {
        "gaps": related_gaps,
        "hypotheses": related_hypotheses,
        "experiment_plans": related_plans,
    }


def build_evidence_chain(result: dict, data: dict[str, Any], max_chars: int = 220) -> dict:
    """Build a readable, compact evidence chain for a search or discovery result."""

    related = get_related_items(
        result,
        data.get("gaps", []),
        data.get("hypotheses", []),
        data.get("experiment_plans", []),
    )
    evidence_ids = _evidence_ids_for_chain(result, related)
    statement_rows = statement_lookup(data.get("statements", pd.DataFrame()))
    paper_titles = {
        str(paper.get("paper_id", "")): str(paper.get("title", "") or paper.get("paper_id", ""))
        for paper in _records(data.get("papers", pd.DataFrame()))
    }
    evidence = []
    missing_ids = []
    for statement_id in evidence_ids:
        statement = statement_rows.get(statement_id)
        if not statement:
            missing_ids.append(statement_id)
            evidence.append(
                {
                    "statement_id": statement_id,
                    "status": "missing",
                    "paper_id": "",
                    "paper_title": "",
                    "statement_type": "",
                    "statement_text": "",
                    "evidence_text": "",
                }
            )
            continue
        paper_id = str(statement.get("paper_id", ""))
        evidence.append(
            {
                "statement_id": statement_id,
                "status": "available",
                "paper_id": paper_id,
                "paper_title": paper_titles.get(paper_id, paper_id),
                "statement_type": statement.get("statement_type", ""),
                "statement_text": _clip_text(str(statement.get("statement_text", "")), max_chars),
                "evidence_text": _clip_text(str(statement.get("evidence_text", "")), max_chars),
            }
        )
    return {
        "result": _summarize_result_for_chain(result, max_chars),
        "evidence": evidence,
        "missing_evidence_ids": missing_ids,
        "gaps": [_summarize_gap_for_chain(gap, max_chars) for gap in related["gaps"]],
        "hypotheses": [
            _summarize_hypothesis_for_chain(hypothesis, max_chars)
            for hypothesis in related["hypotheses"]
        ],
        "experiment_plans": [
            _summarize_plan_for_chain(plan, max_chars)
            for plan in related["experiment_plans"]
        ],
    }


def search_all(query: str, data: dict[str, Any], filters: dict | None = None) -> dict[str, list[dict]]:
    filters = filters or {}
    result_type = filters.get("result_type", "all")
    results = {
        "papers": search_papers(query, data.get("papers", pd.DataFrame())),
        "statements": search_statements(query, data.get("statements", pd.DataFrame()), filters),
        "gaps": search_gaps(query, data.get("gaps", [])),
        "hypotheses": search_hypotheses(query, data.get("hypotheses", [])),
        "experiment_plans": search_experiment_plans(query, data.get("experiment_plans", [])),
    }
    if result_type != "all":
        key = result_type if result_type.endswith("s") else f"{result_type}s"
        return {name: values if name == key else [] for name, values in results.items()}
    return results


def _evidence_ids_for_chain(result: dict, related: dict) -> list[str]:
    candidates: list[object] = []
    if result.get("statement_id"):
        candidates.append(result["statement_id"])
    elif result.get("result_type") == "statement" and result.get("result_id"):
        candidates.append(result["result_id"])
    candidates.extend(result.get("evidence_statement_ids", []) or [])
    for gap in related.get("gaps", []):
        candidates.extend(gap.get("source_statement_ids", []) or [])
    for hypothesis in related.get("hypotheses", []):
        candidates.extend(hypothesis.get("evidence_statement_ids", []) or [])
    evidence_ids = []
    seen = set()
    for candidate in candidates:
        statement_id = str(candidate or "").strip()
        if not statement_id or statement_id in seen:
            continue
        seen.add(statement_id)
        evidence_ids.append(statement_id)
    return evidence_ids


def _summarize_result_for_chain(result: dict, max_chars: int) -> dict:
    result_id = result.get("result_id") or result.get("statement_id") or result.get("hypothesis_id") or ""
    preview = result.get("matched_text") or result.get("evidence_snippet") or result.get("title") or ""
    return {
        "result_type": str(result.get("result_type", "result")),
        "result_id": str(result_id),
        "title": _clip_text(str(result.get("title") or result_id or "Result"), max_chars),
        "preview": _clip_text(str(preview), max_chars),
        "score": result.get("score"),
        "linked_gap_id": result.get("linked_gap_id") or result.get("gap_id", ""),
        "linked_hypothesis_id": result.get("linked_hypothesis_id") or result.get("hypothesis_id", ""),
    }


def _summarize_gap_for_chain(gap: dict, max_chars: int) -> dict:
    return {
        "gap_id": gap.get("gap_id", ""),
        "gap_type": gap.get("gap_type", ""),
        "gap_text": _clip_text(str(gap.get("gap_text", "")), max_chars),
        "source_statement_ids": [str(item) for item in gap.get("source_statement_ids", [])],
        "paper_ids": [str(item) for item in gap.get("paper_ids", [])],
        "rank_score": gap.get("rank_score"),
    }


def _summarize_hypothesis_for_chain(hypothesis: dict, max_chars: int) -> dict:
    return {
        "hypothesis_id": hypothesis.get("hypothesis_id", ""),
        "gap_id": hypothesis.get("gap_id", ""),
        "hypothesis_text": _clip_text(str(hypothesis.get("hypothesis_text", "")), max_chars),
        "confidence_level": hypothesis.get("confidence_level", ""),
        "safety_label": hypothesis.get("safety_label", ""),
        "evidence_statement_ids": [str(item) for item in hypothesis.get("evidence_statement_ids", [])],
        "rationale": _clip_text(str(hypothesis.get("rationale", "")), max_chars),
    }


def _summarize_plan_for_chain(plan_record: dict, max_chars: int) -> dict:
    plan = plan_record.get("plan", {}) or {}
    metrics = plan.get("metrics", [])
    return {
        "hypothesis_id": plan_record.get("hypothesis_id", ""),
        "objective": _clip_text(str(plan.get("objective", "")), max_chars),
        "method": _clip_text(str(plan.get("method", "")), max_chars),
        "baseline_or_control": _clip_text(str(plan.get("baseline_or_control", "")), max_chars),
        "metrics": ", ".join(str(item) for item in metrics) if isinstance(metrics, list) else str(metrics),
        "expected_outcome": _clip_text(str(plan.get("expected_outcome", "")), max_chars),
        "risks_and_limitations": _clip_text(str(plan.get("risks_and_limitations", "")), max_chars),
        "required_data": _clip_text(str(plan.get("required_data", "")), max_chars),
    }


def _evidence_status(evidence_count: int, available_evidence_count: int) -> str:
    if evidence_count <= 0:
        return "missing evidence"
    if available_evidence_count <= 0:
        return "evidence IDs unavailable"
    if available_evidence_count < evidence_count:
        return "partial evidence"
    return "evidence-linked"


def _rank_score_explanation(score_parts: dict[str, int]) -> str:
    parts = [
        f"evidence +{score_parts['evidence']}",
        f"paper coverage +{score_parts['paper_coverage']}",
    ]
    if score_parts["result_limitation_bonus"]:
        parts.append(f"result-with-limitation +{score_parts['result_limitation_bonus']}")
    if score_parts["future_work_bonus"]:
        parts.append(f"future-work evidence +{score_parts['future_work_bonus']}")
    if score_parts["limitation_bonus"]:
        parts.append(f"limitation evidence +{score_parts['limitation_bonus']}")
    return "; ".join(parts)


def _hypothesis_score_explanation(score_parts: dict[str, int]) -> str:
    parts = [
        f"evidence +{score_parts['evidence']}",
        f"paper coverage +{score_parts['paper_coverage']}",
    ]
    if score_parts["confidence"]:
        parts.append(f"confidence +{score_parts['confidence']}")
    if score_parts["safety_label"]:
        parts.append(f"speculative safety label +{score_parts['safety_label']}")
    if score_parts["experiment_plan"]:
        parts.append(f"experiment plan +{score_parts['experiment_plan']}")
    return "; ".join(parts)


def _empty_query(query: str) -> bool:
    return not query or not query.strip()


def _query_terms(query: str) -> list[str]:
    return [term for term in re.findall(r"[a-z0-9]+", query.lower()) if len(term) > 2]


def _match_score(
    query: str,
    text: str,
    result_type: str = "",
    statement_type: str = "",
    has_evidence: bool = False,
) -> float:
    normalized_query = query.lower().strip()
    normalized_text = text.lower()
    if not normalized_query or not normalized_text:
        return 0
    terms = _query_terms(normalized_query)
    matched_terms = {term for term in terms if term in normalized_text}
    exact_bonus = 50 if normalized_query in normalized_text else 0
    if not matched_terms and not exact_bonus:
        return 0
    type_bonus = STATEMENT_TYPE_PRIORITY.get(statement_type, 0)
    result_bonus = {"gap": 5, "hypothesis": 4, "statement": 3, "experiment_plan": 2, "paper": 1}.get(
        result_type,
        0,
    )
    evidence_bonus = 2 if has_evidence else 0
    return exact_bonus + (len(matched_terms) * 5) + type_bonus + result_bonus + evidence_bonus


def _records(data: pd.DataFrame | list[dict]) -> list[dict]:
    if isinstance(data, pd.DataFrame):
        return data.to_dict("records")
    return data


def _plan_text(plan: dict) -> str:
    values = []
    for value in plan.values():
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        else:
            values.append(str(value))
    return " ".join(values)


def _clip_text(text: str, max_chars: int) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _keywords(text: str) -> list[str]:
    tokens = [
        token
        for token in re.findall(r"[a-z][a-z0-9-]{3,}", text.lower())
        if token not in STOPWORDS
    ]
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    return [
        token
        for token, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ][:8]


def _pipeline_status(chunk_count: int, statement_count: int, gap_count: int, hypothesis_count: int) -> str:
    if hypothesis_count:
        return "experiment-ready"
    if gap_count:
        return "gaps-found"
    if statement_count:
        return "statements-extracted"
    if chunk_count:
        return "chunked"
    return "pending"
