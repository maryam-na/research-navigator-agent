# ResearchNavigator Agent Submission

## Summary

ResearchNavigator Agent is a local-first research-discovery assistant for small scientific paper collections. It helps users ingest local papers, extract structured research statements, build a local knowledge graph, discover evidence-backed research gaps, generate speculative hypotheses, draft experiment plans, and evaluate safety and grounding.

The project is designed for the Agents for Good track: it supports responsible research exploration while keeping papers and outputs local.

## Problem

Researchers, students, reviewers, and public-interest teams often need to compare a small set of scientific papers and identify:

- methods
- datasets
- results
- limitations
- future work
- research gaps
- possible next experiments

Manual review is slow, and ungrounded AI summarization can overclaim or invent citations.

## Solution

ResearchNavigator Agent uses deterministic local tools to:

1. Read PDFs from `data/papers/`.
2. Extract text and chunks.
3. Extract and filter structured research statements.
4. Store papers, chunks, and statements in SQLite.
5. Build a NetworkX research graph.
6. Discover gaps from limitations and future-work statements.
7. Generate cautious hypotheses and experiment plans.
8. Evaluate grounding, safety, testability, and traceability.
9. Present the workflow in a local Streamlit dashboard.

## Architecture

The architecture is intentionally local and reviewable:

```text
Local PDFs -> PDF extraction -> statement extraction -> SQLite storage
    -> NetworkX graph -> gap/hypothesis/plan generation
    -> safety and evaluation checks -> Streamlit dashboard
```

The README includes the full Mermaid diagram, setup commands, screenshots, and sample
output gallery. The dashboard's `Pipeline Trace` tab shows the same architecture as a
judge-facing execution story with generated file status, local commands, ADK tool
manifest, MCP tools, safety gates, and final-answer constraints.

## Agent Technology

The project includes a Google ADK-facing agent wrapper in `app/agent.py`. It registers deterministic local function tools from `app/adk_tools.py` for ingestion, graph building, discovery, evaluation, search, evidence inspection, policy checks, summarization, report generation, capability description, and planned tool trajectory.

This makes the agent architecture explicit while preserving the local-first MVP
constraints: no cloud deployment, no model training, and no LLM calls during
deterministic pipeline execution. The agent is meaningful because it coordinates
bounded local tools, applies policy checks, keeps research outputs grounded in
evidence IDs, and exposes the planned trajectory instead of returning an opaque
summary.

## Capstone Concept Coverage

The project demonstrates more than three course concepts:

- **Agent / ADK:** `app/agent.py`, `app/adk_tools.py`, and the `Pipeline Trace` tab.
- **MCP server:** `app/mcp_server.py`, `scripts/run_mcp_server.py`, and `make mcp`.
- **Security features:** prompt-injection, overclaiming, grounding, policy, and
  sensitive-context checks in `tools/safety_tools.py`, `tools/policy_tools.py`,
  `tools/evaluation_tools.py`, and `specs/policies.yaml`.
- **Agent skills:** `SKILL.md`, `.agent/skills/research-navigator/SKILL.md`, and
  `AGENTS.md`.
- **Deployability:** local reproducibility through `make demo`, `make preflight`,
  `make validate`, `make ui`, and `make mcp`.
- **Antigravity:** demonstrated in the video as the agentic coding environment used
  to inspect and validate the project.

The detailed criterion-by-criterion map is in `docs/capstone_evaluation_mapping.md`.

## Why It Matters

The project helps users explore research opportunities without treating generated ideas as facts. Every gap and hypothesis remains tied to local evidence IDs, and evaluation warnings make limitations visible.

## Local-Only Design

- No cloud deployment.
- No external web search.
- No model training or fine-tuning.
- No LLM calls in the deterministic MVP.
- Papers remain in the local repository.
- Outputs are written to `data/processed/`.

## Safety And Evaluation

Safety controls include:

- prompt-injection detection
- overclaiming detection
- evidence-grounding validation
- speculative hypothesis labels
- policy checks for blocked tools and sensitive context
- local paper manifest with license/source notes

Current deterministic evaluation:

```text
Tests: 172 passed
Overall score: 0.917
Grounding score: 0.78
Safety score: 1.0
Testability score: 0.932
Traceability score: 1.0
Golden eval pass rate: 5/5
Preflight: Ready
Submission validator: Ready
```

The evaluation intentionally keeps review warnings visible when evidence diversity is
narrow or experiment plans are structurally complete but still generic.

## How To Run

```bash
make demo
make preflight
make eval
make validate
make ui
```

Or directly:

```bash
uv run python -m scripts.run_demo --reset
uv run python -m scripts.preflight
uv run python -m scripts.run_golden_evals
uv run python -m scripts.validate_submission
uv run streamlit run ui/streamlit_app.py
```

## Key Artifacts

- `README.md`: main project overview.
- `docs/capstone_evaluation_mapping.md`: rubric-to-evidence audit for capstone judging.
- `docs/kaggle_submission_package.md`: long-form written submission package.
- `docs/kaggle_writeup_paste_ready.md`: paste-ready Kaggle writeup.
- `docs/kaggle_video_script.md`: timed video script.
- `docs/kaggle_video_scenario_4min.md`: screen-by-screen recording scenario.
- `SKILL.md`: project skill instructions.
- `AGENTS.md`: shared coding-agent instructions.
- `app/agent.py`: ADK-facing prototype entry point.
- `app/adk_tools.py`: deterministic ADK-facing local tool layer.
- `ui/streamlit_app.py`: local dashboard.
- `docs/screenshots/`: UI screenshots.
- `docs/sample_outputs/`: output excerpts.
- `data/processed/evaluation_report.json`: evaluation report.
- `data/processed/submission_validation_report.json`: readiness report.

## Known Limitations

- Rule-based extraction is intentionally simple.
- No semantic embeddings yet.
- No full citation parser yet.
- The ADK wrapper is prototype-only.
- Experiment plans are structurally useful but can still be generic.
- Grounding currently depends on extracted statement IDs, not full page-level citation metadata.
- Hypotheses and experiment plans require human review before use as research decisions.

## Next Step

The next major upgrade would be full ADK trajectory evaluation and optional human-in-the-loop review gates.
