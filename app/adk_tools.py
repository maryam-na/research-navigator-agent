"""ADK-facing deterministic tool wrappers for ResearchNavigator Agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

from scripts.build_graph import build_graph_from_database
from scripts.discover_gaps import discover_from_database
from scripts.evaluate_outputs import evaluate_from_files
from scripts.ingest_papers import ingest_papers
from scripts.run_demo import run_demo
from tools.policy_tools import validate_tool_action
from tools.storage_tools import get_chunks, get_papers, get_statements
from ui.data_access import (
    create_research_brief,
    evidence_for_statement_ids,
    load_processed_data,
    rank_gaps,
    search_all,
)


DEFAULT_DB_PATH = "data/processed/papers.sqlite"
DEFAULT_GRAPH_PATH = "data/processed/research_graph.graphml"
DEFAULT_DISCOVERY_PATH = "data/processed/gaps_and_hypotheses.json"
DEFAULT_EVALUATION_PATH = "data/processed/evaluation_report.json"

# This manifest is intentionally inspectable: it is used by ADK, Streamlit, tests,
# and MCP docs to show how bounded local tools form an agentic workflow.
ADK_TOOL_MANIFEST = [
    {
        "tool_name": "run_local_demo_pipeline",
        "stage": "orchestration",
        "purpose": "Run the full deterministic local pipeline from papers to evaluated outputs.",
        "inputs": ["reset"],
        "outputs": ["papers", "chunks", "statements", "graph", "gaps", "hypotheses", "evaluation"],
        "safety_gate": "local_files_only",
        "course_concept": "Agent / ADK tool orchestration",
        "policy_boundary": "Runs only repository-local pipeline commands and artifacts.",
    },
    {
        "tool_name": "ingest_local_papers",
        "stage": "ingestion",
        "purpose": "Read local PDFs, extract text, chunk it, filter statements, and store SQLite records.",
        "inputs": ["papers_dir", "db_path", "max_statements_per_type_per_paper"],
        "outputs": ["papers", "chunks", "raw_statements", "saved_statements"],
        "safety_gate": "prompt_injection_treated_as_data",
        "course_concept": "Security features",
        "policy_boundary": "Paper text is treated as data, not executable instructions.",
    },
    {
        "tool_name": "build_local_graph",
        "stage": "knowledge_graph",
        "purpose": "Build a local NetworkX graph from grounded extracted statements.",
        "inputs": ["db_path", "graph_path"],
        "outputs": ["graphml", "node_count", "edge_count", "relation_types"],
        "safety_gate": "graph_size_checked",
        "course_concept": "Tool use",
        "policy_boundary": "Builds graph structure only from stored local records.",
    },
    {
        "tool_name": "discover_local_research_gaps",
        "stage": "research_discovery",
        "purpose": "Create evidence-backed gaps, speculative hypotheses, and experiment plans.",
        "inputs": ["db_path", "output_path", "max_gaps", "max_hypotheses"],
        "outputs": ["gaps", "hypotheses", "experiment_plans"],
        "safety_gate": "evidence_required",
        "course_concept": "Agent / ADK tool orchestration",
        "policy_boundary": "Generated ideas must link back to local statement IDs.",
    },
    {
        "tool_name": "evaluate_local_outputs",
        "stage": "evaluation",
        "purpose": "Score grounding, safety, testability, and traceability for generated outputs.",
        "inputs": ["db_path", "input_path", "output_path"],
        "outputs": ["overall_score", "grounding_score", "safety_score", "failed_checks"],
        "safety_gate": "overclaiming_and_unsupported_claim_checks",
        "course_concept": "Security features",
        "policy_boundary": "Surfaces warnings instead of hiding weak grounding or generic plans.",
    },
    {
        "tool_name": "search_local_corpus",
        "stage": "retrieval",
        "purpose": "Search local papers, statements, gaps, hypotheses, and experiment plans.",
        "inputs": ["query", "result_type", "statement_type"],
        "outputs": ["ranked_local_results"],
        "safety_gate": "local_processed_artifacts_only",
        "course_concept": "Grounded retrieval",
        "policy_boundary": "Searches processed local artifacts rather than external web sources.",
    },
    {
        "tool_name": "inspect_evidence",
        "stage": "grounding",
        "purpose": "Return compact evidence rows for local statement IDs.",
        "inputs": ["statement_ids"],
        "outputs": ["statement_text", "evidence_text", "paper_id", "statement_type"],
        "safety_gate": "evidence_id_traceability",
        "course_concept": "Security features",
        "policy_boundary": "Answers can be traced to local statement IDs and snippets.",
    },
    {
        "tool_name": "summarize_local_project",
        "stage": "status",
        "purpose": "Summarize processed artifacts for concise agent responses.",
        "inputs": [],
        "outputs": ["counts", "top_gap_ids", "evaluation"],
        "safety_gate": "artifact_presence_checked",
        "course_concept": "Agent / ADK tool orchestration",
        "policy_boundary": "Reports local readiness without claiming scientific validity.",
    },
    {
        "tool_name": "generate_local_research_brief",
        "stage": "reporting",
        "purpose": "Generate a local Markdown research brief from deterministic outputs.",
        "inputs": ["output_path"],
        "outputs": ["markdown_brief_path", "characters"],
        "safety_gate": "local_write_path",
        "course_concept": "Agent skills",
        "policy_boundary": "Writes only to a requested local path for human review.",
    },
    {
        "tool_name": "check_local_policy",
        "stage": "policy",
        "purpose": "Check proposed actions against local-first and sensitive-context rules.",
        "inputs": ["tool_name", "action_args"],
        "outputs": ["passed", "failed_checks", "sanitized_args"],
        "safety_gate": "policy_enforcement",
        "course_concept": "Security features",
        "policy_boundary": (
            "Blocks external, deployment, training, email, and unsafe write actions."
        ),
    },
    {
        "tool_name": "describe_agent_capabilities",
        "stage": "agent_story",
        "purpose": (
            "Explain the ADK wrapper, local tools, capstone concept proofs, "
            "and safety boundaries."
        ),
        "inputs": [],
        "outputs": [
            "agent_name",
            "tools",
            "capstone_concept_proofs",
            "orchestration_rationale",
            "safety_boundaries",
        ],
        "safety_gate": "local_capability_disclosure",
        "course_concept": "Agent / ADK tool orchestration",
        "policy_boundary": "Describes local capabilities without invoking external services.",
    },
    {
        "tool_name": "planned_tool_trajectory",
        "stage": "orchestration_explanation",
        "purpose": (
            "Show the deterministic tool path, policy gates, and final-answer "
            "contract for a goal."
        ),
        "inputs": ["user_goal"],
        "outputs": ["steps", "policy_gates", "final_answer_contract"],
        "safety_gate": "policy_gates_visible",
        "course_concept": "Agent / ADK tool orchestration",
        "policy_boundary": "Exposes expected policy gates before any side-effecting action.",
    },
]


CAPSTONE_CONCEPT_PROOFS = [
    {
        "concept": "Agent / ADK",
        "proof": "`app/agent.py` registers a root ADK agent over deterministic local tools.",
        "visible_in": "Pipeline Trace: ADK agent view and tool manifest",
    },
    {
        "concept": "MCP Server",
        "proof": "`app/mcp_server.py` exposes selected local tools through a FastMCP wrapper.",
        "visible_in": "Pipeline Trace: Local MCP server and `make mcp`",
    },
    {
        "concept": "Security features",
        "proof": "Policy, grounding, prompt-injection, and overclaiming checks are callable tools.",
        "visible_in": "Safety & Evaluation and Pipeline Trace safety gates",
    },
    {
        "concept": "Agent skills",
        "proof": "`SKILL.md` and `.agent/skills/research-navigator/SKILL.md` encode local rules.",
        "visible_in": "Pipeline Trace and judge-facing docs",
    },
    {
        "concept": "Deployability",
        "proof": "Makefile targets reproduce the local pipeline, validation, UI, and MCP server.",
        "visible_in": "`make demo`, `make validate`, `make ui`, and `make mcp`",
    },
]


ORCHESTRATION_RATIONALE = [
    {
        "principle": "Tool trajectory before answer",
        "effect": "The agent exposes the expected order from ingestion through evaluation.",
    },
    {
        "principle": "Evidence before speculation",
        "effect": "Gaps and hypotheses are generated only from local statement IDs.",
    },
    {
        "principle": "Policy before side effects",
        "effect": "Blocked actions are checked before any external or unsafe operation.",
    },
    {
        "principle": "Same tools through ADK and MCP",
        "effect": "MCP clients receive bounded local capabilities without new trust rules.",
    },
]


AGENT_TECHNOLOGY_STORY = {
    "agent_name": "research_navigator_agent",
    "agent_framework": "Google ADK",
    "mode": "local deterministic MVP",
    "model_policy": "No LLM calls are made by deterministic scripts or tests; ADK wrapper is ready for local orchestration.",
    "orchestration_pattern": "ADK-facing function tools over deterministic local pipeline modules.",
    "course_concepts": [
        "tool orchestration",
        "agent instruction and policy boundaries",
        "grounded retrieval over local artifacts",
        "safety checks before generated claims",
        "evaluation and traceability",
    ],
    "capstone_concept_proofs": CAPSTONE_CONCEPT_PROOFS,
    "orchestration_rationale": ORCHESTRATION_RATIONALE,
    "safety_boundaries": [
        "Paper text is treated as untrusted data, not instructions.",
        "Outputs must reference local statement IDs.",
        "Hypotheses are labeled speculative and cannot be phrased as proven discoveries.",
        "External browsing, deployment, email, and model training are blocked for the MVP.",
    ],
    "human_review_gates": [
        "adding or replacing papers",
        "exporting reports",
        "using generated hypotheses outside the prototype",
        "expanding beyond the 5-10 paper MVP corpus",
    ],
}


def run_local_demo_pipeline(reset: bool = False) -> dict[str, Any]:
    """Run the full deterministic local pipeline."""

    return run_demo(reset=reset)


def describe_agent_capabilities() -> dict[str, Any]:
    """Describe the ADK-facing local agent wrapper and callable deterministic tools."""

    return {
        **AGENT_TECHNOLOGY_STORY,
        "tools": ADK_TOOL_MANIFEST,
        "tool_count": len(ADK_TOOL_MANIFEST),
    }


def planned_tool_trajectory(user_goal: str = "discover grounded research gaps") -> dict[str, Any]:
    """Return the deterministic tool trajectory the ADK wrapper exposes for a research goal."""

    steps = [
        {
            "order": index + 1,
            "tool_name": tool["tool_name"],
            "stage": tool["stage"],
            "why": _trajectory_reason(str(tool["stage"]), user_goal),
            "safety_gate": tool["safety_gate"],
            "policy_boundary": tool["policy_boundary"],
        }
        for index, tool in enumerate(ADK_TOOL_MANIFEST[:5])
    ]
    steps.extend(
        [
            {
                "order": 6,
                "tool_name": "search_local_corpus",
                "stage": "retrieval",
                "why": "Answer user questions from processed local evidence after the pipeline is complete.",
                "safety_gate": "local_processed_artifacts_only",
                "policy_boundary": "Searches only the local processed corpus.",
            },
            {
                "order": 7,
                "tool_name": "inspect_evidence",
                "stage": "grounding",
                "why": "Show statement-level evidence for any gap, hypothesis, or answer.",
                "safety_gate": "evidence_id_traceability",
                "policy_boundary": "Keeps answers traceable to local statement IDs.",
            },
            {
                "order": 8,
                "tool_name": "check_local_policy",
                "stage": "policy",
                "why": "Block actions outside the local-first MVP boundary before execution.",
                "safety_gate": "policy_enforcement",
                "policy_boundary": (
                    "Rejects cloud, email, external browsing, training, and unsafe writes."
                ),
            },
        ]
    )
    return {
        "user_goal": user_goal,
        "trajectory_type": "deterministic_adk_tool_plan",
        "why_this_is_agentic": (
            "The ADK wrapper exposes a tool trajectory, policy gates, evidence inspection, "
            "and final-answer contract instead of returning an opaque summary."
        ),
        "steps": steps,
        "policy_gates": [
            "paper_text_is_untrusted_data",
            "local_artifacts_only",
            "evidence_ids_required",
            "speculative_hypotheses_labeled",
            "external_actions_policy_checked",
        ],
        "final_answer_contract": [
            "cite local artifact paths or statement IDs",
            "separate evidence-backed findings from speculative hypotheses",
            "include evaluation warnings when relevant",
            "state when human review is required",
        ],
    }


def _trajectory_reason(stage: str, user_goal: str) -> str:
    reasons = {
        "orchestration": f"Coordinate the local workflow needed to {user_goal}.",
        "ingestion": "Convert local PDFs into structured, queryable records.",
        "knowledge_graph": "Connect papers and statements into a visualizable research graph.",
        "research_discovery": "Generate evidence-backed gaps, hypotheses, and experiment plans.",
        "evaluation": "Check grounding, safety, testability, and traceability before presentation.",
    }
    return reasons.get(stage, "Support the local research-discovery workflow.")


def ingest_local_papers(
    papers_dir: str = "data/papers",
    db_path: str = DEFAULT_DB_PATH,
    max_statements_per_type_per_paper: int = 30,
) -> dict[str, Any]:
    """Ingest local PDFs and save filtered deterministic statements."""

    summary = ingest_papers(
        papers_dir,
        db_path,
        extract_statements=True,
        filter_extracted_statements=True,
        max_statements_per_type_per_paper=max_statements_per_type_per_paper,
    )
    return {
        "papers": summary.papers,
        "chunks": summary.chunks,
        "skipped_files": summary.skipped_files,
        "raw_statements": summary.raw_statements,
        "saved_statements": summary.statements,
    }


def build_local_graph(
    db_path: str = DEFAULT_DB_PATH,
    graph_path: str = DEFAULT_GRAPH_PATH,
) -> dict[str, Any]:
    """Build and export the local NetworkX research graph."""

    return build_graph_from_database(db_path, graph_path)


def discover_local_research_gaps(
    db_path: str = DEFAULT_DB_PATH,
    output_path: str = DEFAULT_DISCOVERY_PATH,
    max_gaps: int = 10,
    max_hypotheses: int = 10,
) -> dict[str, Any]:
    """Discover gaps, hypotheses, and experiment plans from stored statements."""

    payload = discover_from_database(
        db_path,
        output_path,
        max_gaps=max_gaps,
        max_hypotheses=max_hypotheses,
    )
    return payload["counts"]


def evaluate_local_outputs(
    db_path: str = DEFAULT_DB_PATH,
    input_path: str = DEFAULT_DISCOVERY_PATH,
    output_path: str = DEFAULT_EVALUATION_PATH,
) -> dict[str, Any]:
    """Evaluate generated outputs for grounding, safety, testability, and traceability."""

    return evaluate_from_files(db_path, input_path, output_path)


def search_local_corpus(query: str, result_type: str = "all", statement_type: str = "all") -> dict[str, Any]:
    """Search papers, statements, gaps, hypotheses, and experiment plans."""

    data = load_processed_data(
        DEFAULT_DB_PATH,
        gaps_path=DEFAULT_DISCOVERY_PATH,
        evaluation_path=DEFAULT_EVALUATION_PATH,
        graph_path=DEFAULT_GRAPH_PATH,
    )
    results = search_all(
        query,
        data,
        {
            "result_type": result_type,
            "statement_type": statement_type,
            "paper_id": "all",
        },
    )
    return {key: values[:10] for key, values in results.items()}


def inspect_evidence(statement_ids: list[str]) -> dict[str, Any]:
    """Return compact evidence rows for local statement IDs."""

    statements = get_statements(DEFAULT_DB_PATH) if Path(DEFAULT_DB_PATH).exists() else []
    return {"evidence": evidence_for_statement_ids(statement_ids, statements)}


def summarize_local_project() -> dict[str, Any]:
    """Summarize local processed artifacts for agent responses."""

    papers = get_papers(DEFAULT_DB_PATH) if Path(DEFAULT_DB_PATH).exists() else []
    chunks = get_chunks(DEFAULT_DB_PATH) if Path(DEFAULT_DB_PATH).exists() else []
    statements = get_statements(DEFAULT_DB_PATH) if Path(DEFAULT_DB_PATH).exists() else []
    data = load_processed_data(
        DEFAULT_DB_PATH,
        gaps_path=DEFAULT_DISCOVERY_PATH,
        evaluation_path=DEFAULT_EVALUATION_PATH,
        graph_path=DEFAULT_GRAPH_PATH,
    )
    graph = data.get("graph", nx.DiGraph())
    ranked_gaps = rank_gaps(data.get("gaps", []), pd.DataFrame(statements))
    return {
        "papers": len(papers),
        "chunks": len(chunks),
        "statements": len(statements),
        "graph_nodes": graph.number_of_nodes(),
        "graph_edges": graph.number_of_edges(),
        "gaps": len(data.get("gaps", [])),
        "hypotheses": len(data.get("hypotheses", [])),
        "top_gap_ids": [gap.get("gap_id") for gap in ranked_gaps[:3]],
        "evaluation": data.get("evaluation", {}),
    }


def generate_local_research_brief(output_path: str = "data/processed/researchnavigator_brief.md") -> dict[str, Any]:
    """Generate a local Markdown research brief from processed artifacts."""

    data = load_processed_data(
        DEFAULT_DB_PATH,
        gaps_path=DEFAULT_DISCOVERY_PATH,
        evaluation_path=DEFAULT_EVALUATION_PATH,
        graph_path=DEFAULT_GRAPH_PATH,
    )
    brief = create_research_brief(data)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(brief, encoding="utf-8")
    return {"output_path": str(path), "characters": len(brief)}


def check_local_policy(tool_name: str, action_args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate a proposed local tool action against deterministic policy rules."""

    return validate_tool_action(tool_name, action_args or {})
