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
        papers = sorted({str(lookup[item].get("paper_id", "")) for item in source_ids if item in lookup})
        source_types = sorted({str(lookup[item].get("statement_type", "")) for item in source_ids if item in lookup})
        score = (
            len(source_ids) * 3
            + len(papers) * 2
            + (2 if gap.get("gap_type") == "result_with_limitation" else 0)
            + (1 if "future_work" in source_types else 0)
            + (1 if "limitation" in source_types else 0)
        )
        ranked.append(
            {
                **gap,
                "rank_score": score,
                "evidence_count": len(source_ids),
                "paper_count": len(papers),
                "source_statement_types": source_types,
            }
        )
    return sorted(
        ranked,
        key=lambda item: (-int(item.get("rank_score", 0)), str(item.get("gap_id", ""))),
    )


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
