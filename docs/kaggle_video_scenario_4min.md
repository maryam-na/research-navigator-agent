# Four-Minute Kaggle Video Scenario

Target length: 4:30. Hard limit: under 5:00.

Use this file for recording only. Do not paste this text into the Kaggle Writeup.

## Before Recording

Prepare these windows:

1. Terminal in the project folder.
2. Browser open to the Streamlit local URL.
3. Antigravity open on the project folder.
4. Optional editor tab open to `app/agent.py`, `app/adk_tools.py`, and
   `app/mcp_server.py`.

Run these commands before recording so the demo uses fresh local artifacts:

```bash
make demo
make preflight
make validate
```

Start the dashboard:

```bash
make ui
```

Optional MCP proof command:

```bash
uv run python -c "from app.mcp_server import mcp_tool_manifest; print(mcp_tool_manifest())"
```

Claim guardrails:

- Do not claim public deployment. Say the project is locally reproducible.
- Do not claim Antigravity is code evidence. Show it briefly in the video.
- Do not claim the deterministic MVP makes LLM calls during pipeline execution.
- Do not call hypotheses discoveries. Say speculative, evidence-linked hypotheses.
- Do not quote stale metrics unless `make validate` or the relevant command was rerun.

## 0:00-0:20 Opening

Screen: Streamlit Overview or Search page, zoomed so text is readable.

Say:

Hi, this is ResearchNavigator Agent, my Agents for Good capstone project. It is a
local-first research-discovery assistant that helps users turn a small set of papers
into evidence-backed gaps, speculative hypotheses, experiment plans, and safety
evaluation reports.

## 0:20-0:45 Problem And Value

Screen: Overview counts or the local `data/papers/` folder.

Say:

Researchers and students often compare papers manually. A generic chatbot may produce
fluent summaries, but it can lose grounding, overclaim, or invent citations. This
project focuses on a safer workflow: local papers, local storage, evidence IDs,
visible warnings, and human review.

## 0:45-1:10 Architecture And Reproducibility

Screen: terminal with recent `make demo` result, or README architecture diagram.

Say:

The backend pipeline runs locally. It parses PDFs, chunks text, extracts structured
statements, stores them in SQLite, builds a NetworkX research graph, discovers gaps,
generates cautious hypotheses and experiment plans, and evaluates the results.

Show:

```bash
make demo
```

## 1:10-1:55 Dashboard And Evidence

Screen: Search tab, then Evidence Inspector.

Say:

The dashboard is a research discovery workspace. Search covers papers, extracted
statements, gaps, hypotheses, and plans. In the Evidence Inspector, each statement
shows its source paper, statement type, chunk ID, evidence snippet, quality signals,
and linked discoveries. This makes the output traceable instead of just fluent.

## 1:55-2:35 Gaps, Hypotheses, And Plans

Screen: Discoveries tab. Open one gap, one hypothesis, and its experiment plan.

Say:

The system ranks candidate research gaps only when local evidence exists, such as a
limitation or future-work statement. Each gap shows supporting statement IDs.
Hypotheses are labeled as speculative research hypotheses, not proven discoveries.
The linked experiment plan includes objective, required data, method, baseline,
metrics, expected outcome, and risks.

## 2:35-3:10 Agent Technology: ADK

Screen: Pipeline Trace, then briefly show `app/agent.py` and `app/adk_tools.py`.

Say:

The project includes a Google ADK-facing agent wrapper. The agent exposes deterministic
local tools for ingestion, graph building, discovery, evaluation, search, evidence
inspection, policy checking, and brief generation. Pipeline Trace shows the tool
manifest, planned trajectory, safety gates, and final answer contract.

## 3:10-3:35 MCP And Skills

Screen: Pipeline Trace MCP section, then briefly show `app/mcp_server.py` and `SKILL.md`.

Say:

The local MCP server wrapper exposes selected ResearchNavigator tools to MCP-compatible
clients while keeping the same local-first safety boundaries. The reusable `SKILL.md`
documents expected agent behavior, constraints, the tool map, and safety rules.

Optional command to show:

```bash
uv run python -c "from app.mcp_server import mcp_tool_manifest; print(mcp_tool_manifest())"
```

## 3:35-4:05 Safety And Evaluation

Screen: Safety & Evaluation tab.

Say:

Safety is built into the product. The system checks prompt-injection phrases in papers,
overclaiming, unsupported hypotheses, grounding, testability, and traceability. The
deterministic checks pass, and warnings remain visible when evidence diversity or plan
specificity needs review.

## 4:05-4:30 Antigravity And Local Deployability

Screen: Antigravity with this project open and terminal output from `make preflight`
or `make validate`.

Say:

I used Antigravity as the agentic coding environment to inspect the codebase, run
local validation commands, and iterate on the ADK/MCP wrapper and Streamlit demo.
For deployability, this project is reproducible locally with Makefile targets such as
`make demo`, `make ui`, `make preflight`, `make validate`, and `make mcp`.

## 4:30-4:45 Closing

Screen: dashboard Overview, Search, or Pipeline Trace.

Say:

ResearchNavigator is local-first, evidence-backed, policy-gated, and evaluated. It
helps make research exploration more responsible while keeping the human in control
of interpretation.

## Recording Checklist

- App shown, not only code.
- Problem and value stated in the first 45 seconds.
- Architecture explained with SQLite, NetworkX, local pipeline, and Streamlit.
- Search and Evidence Inspector shown.
- Discoveries show evidence IDs and speculative hypothesis labels.
- Pipeline Trace shown for ADK tool manifest and trajectory.
- MCP wrapper shown through Pipeline Trace, `app/mcp_server.py`, or manifest command.
- `SKILL.md` shown or mentioned for agent skills.
- Safety & Evaluation tab shown.
- Antigravity shown for 15-25 seconds with a local command result.
- Local reproducibility shown with at least one Makefile command result.
- No terminal tracebacks or empty dashboard states visible.
- Final runtime stays under 5:00.

## If Running Long

Cut in this order:

1. Skip opening code files and rely on Pipeline Trace for ADK/MCP visibility.
2. Skip the optional MCP manifest command.
3. Show only one discovery card instead of a gap, hypothesis, and plan separately.
4. Shorten the closing to one sentence.
