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

## Agent Technology

The project includes a Google ADK-facing agent wrapper in `app/agent.py`. It registers deterministic local function tools from `app/adk_tools.py` for ingestion, graph building, discovery, evaluation, search, evidence inspection, policy checks, summarization, report generation, capability description, and planned tool trajectory.

This makes the agent architecture explicit while preserving the local-first MVP constraints: no cloud deployment, no model training, and no LLM calls during deterministic pipeline execution. The dashboard’s `Pipeline Trace` tab shows the ADK agent view, tool manifest, planned trajectory, and safety gate for each stage.

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
Overall score: 0.917
Grounding score: 0.78
Safety score: 1.0
Testability score: 0.932
Traceability score: 1.0
Golden eval pass rate: 5/5
Submission validator: Ready
```

## How To Run

```bash
make demo
make eval
make validate
make ui
```

Or directly:

```bash
uv run python -m scripts.run_demo --reset
uv run python -m scripts.run_golden_evals
uv run python -m scripts.validate_submission
uv run streamlit run ui/streamlit_app.py
```

## Key Artifacts

- `README.md`: main project overview.
- `docs/capstone_evaluation_mapping.md`: rubric-to-evidence audit for capstone judging.
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

## Next Step

The next major upgrade would be full ADK trajectory evaluation and optional human-in-the-loop review gates.
