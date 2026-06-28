# Four-Minute Kaggle Video Scenario

Target length: about 4 minutes.

Use this file for recording only. Do not paste this text into the Kaggle Writeup.

## Before Recording

Prepare these windows:

1. Terminal in the project folder.
2. Streamlit dashboard running with:

```bash
make ui
```

3. Antigravity open on the project folder.
4. Browser open to the Streamlit local URL.

Optional pre-run commands:

```bash
make demo
make preflight
make validate
```

## 0:00-0:20 Opening

Screen: show the Streamlit Overview or Search page.

Say:

Hi, this is ResearchNavigator Agent, my Agents for Good capstone project. It is a local-first research-discovery assistant that helps users turn a small set of scientific papers into evidence-backed research gaps, speculative hypotheses, experiment plans, and safety evaluation reports.

## 0:20-0:50 Problem

Screen: show local papers or the Overview counts.

Say:

Researchers and students often need to compare several papers manually. They need to identify methods, datasets, results, limitations, and future-work directions. A normal chatbot can summarize papers, but it may lose grounding, overclaim, or invent citations. ResearchNavigator focuses on a safer workflow: local papers, local storage, evidence IDs, and visible warnings.

## 0:50-1:20 Local Pipeline

Screen: show terminal or Pipeline Trace.

Say:

The backend pipeline runs locally. It ingests PDFs, extracts text, chunks the content, extracts structured research statements, deduplicates and filters noisy statements, stores everything in SQLite, builds a NetworkX knowledge graph, discovers research gaps, generates cautious hypotheses and experiment plans, and evaluates the results.

Show command:

```bash
make demo
```

## 1:20-1:55 Dashboard And Evidence

Screen: show Search, then Evidence Inspector.

Say:

The dashboard is designed as a research discovery workspace. In Search, I can explore papers, extracted statements, gaps, hypotheses, and experiment plans. In the Evidence Inspector, each statement shows its source paper, statement type, chunk ID, evidence snippet, quality signals, and linked discoveries. This makes the output traceable instead of just fluent.

## 1:55-2:30 Gaps, Hypotheses, And Plans

Screen: show Discoveries tab and a hypothesis or experiment plan.

Say:

Here, the system ranks candidate research gaps. Each gap is created only when there is source evidence, such as a limitation or future-work statement. Hypotheses are labeled as speculative research hypotheses, not proven discoveries. Each one links back to evidence statement IDs and includes an experiment plan with objective, required data, method, baseline, metrics, expected outcome, and risks.

## 2:30-3:00 Agent Technology: ADK

Screen: show Pipeline Trace, then briefly show `app/agent.py` and `app/adk_tools.py`.

Say:

The project includes a Google ADK-facing agent wrapper. The agent exposes deterministic local tools for ingestion, graph building, discovery, evaluation, search, evidence inspection, policy checking, and research brief generation. The Pipeline Trace tab shows the tool manifest, planned tool trajectory, safety gates, and final answer contract.

## 3:00-3:25 MCP And Skills

Screen: show `app/mcp_server.py`, then the Pipeline Trace MCP section.

Say:

I also added a local MCP server wrapper, which exposes selected ResearchNavigator tools to MCP-compatible clients while keeping the same local-first safety boundaries. The project also includes a reusable `SKILL.md`, so the expected agent behavior, constraints, tool map, and safety rules are documented.

Optional command to show:

```bash
uv run python -c "from app.mcp_server import mcp_tool_manifest; print(mcp_tool_manifest())"
```

## 3:25-3:45 Safety And Evaluation

Screen: show Safety & Evaluation tab.

Say:

Safety is part of the product. The system checks prompt-injection phrases in papers, overclaiming, unsupported hypotheses, evidence grounding, testability, and traceability. Current deterministic evaluation reports a strong overall score, and warnings remain visible when evidence diversity or plan specificity needs improvement.

## 3:45-4:00 Antigravity And Closing

Screen: show Antigravity with the project open and a terminal result such as `make preflight`.

Say:

I used Antigravity as the agentic coding environment to inspect the codebase, run local validation commands, and iterate on the ADK and MCP wrapper and Streamlit demo. ResearchNavigator is local-first, evidence-backed, policy-gated, and evaluated, making research exploration more responsible while keeping the human in control.

## Recording Checklist

- Show the app, not only code.
- Show ADK files: `app/agent.py` and `app/adk_tools.py`.
- Show MCP file: `app/mcp_server.py`.
- Show Antigravity briefly.
- Show at least one safety/evaluation screen.
- Keep the final video under 5 minutes.
