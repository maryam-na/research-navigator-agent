# Agent Technology Story

ResearchNavigator Agent demonstrates agent concepts through a local Google ADK-facing wrapper over deterministic research-discovery tools.

## What The Agent Does

The agent helps a user move from local scientific papers to grounded research ideas:

1. Ingest local PDFs.
2. Extract and filter structured research statements.
3. Store evidence in SQLite.
4. Build a NetworkX knowledge graph.
5. Discover evidence-backed gaps.
6. Generate speculative hypotheses and experiment plans.
7. Evaluate grounding, safety, testability, and traceability.
8. Search and inspect evidence through the dashboard.

## How ADK Is Used

`app/agent.py` defines the ADK-facing `root_agent` when Google ADK is available. The agent registers function tools from `app/adk_tools.py`.

The local tool layer exposes:

- `run_local_demo_pipeline`
- `ingest_local_papers`
- `build_local_graph`
- `discover_local_research_gaps`
- `evaluate_local_outputs`
- `search_local_corpus`
- `inspect_evidence`
- `summarize_local_project`
- `generate_local_research_brief`
- `check_local_policy`
- `describe_agent_capabilities`
- `planned_tool_trajectory`

The project also includes a local MCP server wrapper:

- `app/mcp_server.py`
- `scripts/run_mcp_server.py`

Run it with:

```bash
make mcp
```

## Why This Still Counts As Agentic

The MVP emphasizes controlled agent behavior over opaque generation. It demonstrates:

- tool orchestration
- an explicit agent instruction
- local policy boundaries
- retrieval over local processed artifacts
- evidence inspection
- grounded output contracts
- safety and evaluation checks
- visible tool trajectory
- MCP-compatible tool exposure

The deterministic implementation makes the demo reproducible for judges while preserving a clear path to fuller ADK orchestration later.

## Safety Boundaries

- Paper text is treated as untrusted data.
- Generated gaps and hypotheses must cite local statement IDs.
- Hypotheses are labeled speculative.
- Overclaiming and prompt-injection patterns are checked.
- External browsing, deployment, email, and model training are blocked in the MVP.

## Where Judges Can See It

Open the Streamlit dashboard and go to:

```text
Pipeline Trace
```

That tab shows:

- ADK agent view
- callable tool manifest
- capstone concept proof points
- planned deterministic tool trajectory
- per-stage safety gates
- policy and human-review gates
- final answer contract

## Implementation Proof Points

- The ADK manifest includes tool stages, course-concept labels, policy boundaries,
  inputs, outputs, and safety gates.
- The planned trajectory explains why each step exists before the agent presents an
  answer.
- The MCP manifest exposes stage and safety-gate metadata for the selected local tools.
- The final answer contract requires local artifact paths or statement IDs, separation
  of evidence from speculation, visible evaluation warnings, and human-review notes.
