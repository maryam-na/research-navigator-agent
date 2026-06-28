# Kaggle Public Video Script

Target length: 4:30. Hard limit: under 5:00.

Use this as the spoken script. Use `docs/kaggle_video_scenario_4min.md` as the
screen-by-screen recording checklist.

## Recording Goal

The video must show the problem, solution, agent value, architecture, working demo,
build tools, Antigravity usage, and local deployability. Keep the claims conservative:

- Say local reproducibility, not public cloud deployment.
- Say ADK-facing wrapper, not production-hosted ADK service.
- Say hypotheses are speculative, not proven discoveries.
- Say Antigravity is demonstrated in the video, not as a code artifact.
- Use current command results only after rerunning them before recording.

## 0:00-0:20 Opening

Hi, this is ResearchNavigator Agent, my Agents for Good capstone project. It is a
local-first research-discovery assistant that helps users move from a small set of
scientific papers to evidence-backed gaps, speculative hypotheses, experiment plans,
and safety evaluation reports.

## 0:20-0:45 Problem And Value

Researchers and students often compare papers by hand. They need methods, datasets,
results, limitations, and future-work ideas, but generic chatbots can lose grounding,
overclaim, or invent citations. ResearchNavigator focuses on a safer workflow:
local papers, local storage, evidence IDs, visible warnings, and human review.

## 0:45-1:10 Architecture And Reproducibility

The architecture is intentionally local. PDFs are parsed into chunks, structured
statements are stored in SQLite, a NetworkX graph connects the research entities,
and deterministic discovery tools generate gaps, hypotheses, plans, and evaluation
reports. I can reproduce the demo with:

```bash
make demo
```

## 1:10-1:55 Dashboard And Evidence

Now I open the local Streamlit dashboard with:

```bash
make ui
```

In Search, I can explore papers, extracted statements, gaps, hypotheses, and plans.
In the Evidence Inspector, each statement keeps its source paper, chunk ID, compact
evidence snippet, quality signals, and linked discoveries. This is the core user
benefit: the output is traceable, not just fluent.

## 1:55-2:35 Gaps, Hypotheses, And Plans

In Discoveries, the system ranks candidate research gaps from local limitation and
future-work evidence. Each gap shows supporting statement IDs. Hypotheses are clearly
labeled as speculative research hypotheses, and each one links to an experiment plan
with objective, required data, method, baseline, metrics, expected outcome, and risks.

## 2:35-3:10 Agent Technology: ADK

The agent value is tool orchestration with boundaries. The project includes a Google
ADK-facing wrapper in `app/agent.py` and deterministic local tools in `app/adk_tools.py`.
The Pipeline Trace tab shows the callable tool manifest, planned trajectory, safety
gates, and final answer contract, so judges can inspect the agent workflow directly.

## 3:10-3:35 MCP And Skills

The same local capabilities are also exposed through a local MCP server wrapper in
`app/mcp_server.py`. I can show the MCP tool manifest with:

```bash
uv run python -c "from app.mcp_server import mcp_tool_manifest; print(mcp_tool_manifest())"
```

The project also includes `SKILL.md`, which documents the reusable agent behavior,
tool map, constraints, and safety rules.

## 3:35-4:05 Safety And Evaluation

Safety is part of the product. The Safety & Evaluation tab checks prompt-injection
phrases in papers, overclaiming, unsupported hypotheses, grounding, testability, and
traceability. The deterministic checks pass, and warnings remain visible when evidence
diversity or plan specificity needs review.

## 4:05-4:30 Antigravity And Local Deployability

Finally, I show this project open in Antigravity with a local terminal result such as:

```bash
make preflight
```

or:

```bash
make validate
```

This demonstrates how I used Antigravity as the agentic coding environment to inspect
the codebase, run local validation, and iterate on the ADK/MCP wrapper and dashboard.

## 4:30-4:45 Closing

ResearchNavigator Agent is local-first, evidence-backed, policy-gated, and evaluated.
It is designed to make research exploration more responsible by keeping outputs tied
to source evidence and by making limitations visible.
