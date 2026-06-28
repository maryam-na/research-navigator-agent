# Kaggle Public Video Script

Target length: about 4 minutes.

For the detailed screen-by-screen recording scenario, see:

```text
docs/kaggle_video_scenario_4min.md
```

## 0:00 - Opening

Hi, this is ResearchNavigator Agent, my Agents for Good capstone project. It is a local-first research-discovery assistant that helps users move from a small set of scientific papers to evidence-backed research gaps, speculative hypotheses, and experiment plans.

## 0:20 - Problem

Researchers and students often need to compare several papers manually. They need to find methods, datasets, results, limitations, and future-work ideas. A normal chatbot can summarize papers, but it may overclaim, lose grounding, or send private documents to external services.

## 0:45 - Local Pipeline

This project runs locally. I can run the full backend with:

```bash
make demo
```

The pipeline ingests local PDFs, extracts text, chunks it, extracts structured statements, stores them in SQLite, builds a NetworkX graph, discovers research gaps, generates hypotheses and experiment plans, and evaluates the outputs.

## 1:15 - Dashboard

Now I open the Streamlit dashboard with:

```bash
make ui
```

The Search tab lets me search across the local corpus and generated outputs. The Evidence Inspector shows source statements, evidence snippets, quality signals, and linked discoveries.

## 1:45 - Gaps And Hypotheses

In Discoveries, the system ranks research gaps and shows the evidence statement IDs behind each one. Hypotheses are clearly labeled as speculative, not proven discoveries. Each hypothesis is connected to an experiment plan.

## 2:15 - ADK Agent Story

In Pipeline Trace, I show the ADK agent view. The project has a Google ADK-facing wrapper in `app/agent.py` and deterministic local tools in `app/adk_tools.py`. This tab shows the callable tool manifest, planned tool trajectory, and safety gate for each step.

## 2:45 - MCP And Antigravity

I also added a local MCP server wrapper in `app/mcp_server.py`, which exposes selected deterministic tools to MCP-compatible clients. I can show the local tool manifest with:

```bash
uv run python -c "from app.mcp_server import mcp_tool_manifest; print(mcp_tool_manifest())"
```

For Antigravity, I show this same project open in the Antigravity workspace, with the local terminal running `make preflight` or `make ci`. This demonstrates how I used the agentic coding environment to inspect the project, validate the implementation, and iterate on the ADK/MCP wrapper and dashboard.

## 3:20 - Safety And Evaluation

The Safety & Evaluation tab shows grounding, safety, testability, and traceability. Current results pass deterministic checks, with warnings shown when evidence diversity or plan specificity could be improved.

## 3:50 - Closing

ResearchNavigator Agent is local-first, evidence-backed, policy-gated, and evaluated. It is designed to make research exploration more responsible by keeping outputs connected to source evidence and by making limitations visible.
