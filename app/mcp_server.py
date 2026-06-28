"""Local MCP server wrapper for ResearchNavigator deterministic tools."""

from __future__ import annotations

from typing import Any, Callable

from app.adk_tools import (
    check_local_policy,
    describe_agent_capabilities,
    generate_local_research_brief,
    inspect_evidence,
    planned_tool_trajectory,
    search_local_corpus,
    summarize_local_project,
)


MCP_SERVER_NAME = "research-navigator-agent"

MCP_TOOL_SPECS = [
    {
        "name": "describe_agent_capabilities",
        "description": "Describe the local ADK-facing ResearchNavigator agent and its tools.",
        "stage": "agent_story",
        "safety_gate": "local_capability_disclosure",
    },
    {
        "name": "planned_tool_trajectory",
        "description": "Return the deterministic tool trajectory for a research-discovery goal.",
        "stage": "orchestration",
        "safety_gate": "policy_gates_visible",
    },
    {
        "name": "summarize_local_project",
        "description": "Summarize local processed papers, statements, graph, discoveries, and evaluation.",
        "stage": "status",
        "safety_gate": "artifact_presence_checked",
    },
    {
        "name": "search_local_corpus",
        "description": "Search local processed papers, statements, gaps, hypotheses, and plans.",
        "stage": "retrieval",
        "safety_gate": "local_processed_artifacts_only",
    },
    {
        "name": "inspect_evidence",
        "description": "Return compact evidence rows for local statement IDs.",
        "stage": "grounding",
        "safety_gate": "evidence_id_traceability",
    },
    {
        "name": "generate_local_research_brief",
        "description": "Generate a local Markdown research brief from processed artifacts.",
        "stage": "reporting",
        "safety_gate": "local_write_path",
    },
    {
        "name": "check_local_policy",
        "description": "Check proposed tool actions against local-first policy rules.",
        "stage": "policy",
        "safety_gate": "policy_enforcement",
    },
]


def mcp_tool_manifest() -> list[dict[str, str]]:
    """Return the local MCP tools exposed by this wrapper."""

    return [dict(tool) for tool in MCP_TOOL_SPECS]


def register_mcp_tools(server: Any) -> Any:
    """Register ResearchNavigator tools on a FastMCP-compatible server."""

    _register(
        server,
        "describe_agent_capabilities",
        "Describe the local ADK-facing ResearchNavigator agent and its tools.",
        describe_agent_capabilities,
    )

    def planned_tool_trajectory_tool(user_goal: str = "discover grounded research gaps") -> dict[str, Any]:
        return planned_tool_trajectory(user_goal)

    _register(
        server,
        "planned_tool_trajectory",
        "Return the deterministic tool trajectory for a research-discovery goal.",
        planned_tool_trajectory_tool,
    )
    _register(
        server,
        "summarize_local_project",
        "Summarize local processed papers, statements, graph, discoveries, and evaluation.",
        summarize_local_project,
    )

    def search_local_corpus_tool(
        query: str,
        result_type: str = "all",
        statement_type: str = "all",
    ) -> dict[str, Any]:
        return search_local_corpus(query, result_type=result_type, statement_type=statement_type)

    _register(
        server,
        "search_local_corpus",
        "Search local processed papers, statements, gaps, hypotheses, and plans.",
        search_local_corpus_tool,
    )

    def inspect_evidence_tool(statement_ids: list[str]) -> dict[str, Any]:
        return inspect_evidence(statement_ids)

    _register(
        server,
        "inspect_evidence",
        "Return compact evidence rows for local statement IDs.",
        inspect_evidence_tool,
    )

    def generate_local_research_brief_tool(
        output_path: str = "data/processed/researchnavigator_brief.md",
    ) -> dict[str, Any]:
        return generate_local_research_brief(output_path)

    _register(
        server,
        "generate_local_research_brief",
        "Generate a local Markdown research brief from processed artifacts.",
        generate_local_research_brief_tool,
    )

    def check_local_policy_tool(
        tool_name: str,
        action_args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return check_local_policy(tool_name, action_args or {})

    _register(
        server,
        "check_local_policy",
        "Check proposed tool actions against local-first policy rules.",
        check_local_policy_tool,
    )
    return server


def create_mcp_server() -> Any:
    """Create a local FastMCP server exposing ResearchNavigator tools."""

    from mcp.server.fastmcp import FastMCP

    server = FastMCP(MCP_SERVER_NAME)
    return register_mcp_tools(server)


def _register(server: Any, name: str, description: str, func: Callable[..., dict[str, Any]]) -> None:
    server.tool(name=name, description=description)(func)


if __name__ == "__main__":
    create_mcp_server().run()
