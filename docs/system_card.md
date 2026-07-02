# ResearchNavigator Agent System Card

## System Name

ResearchNavigator Agent

## Intended Use

ResearchNavigator Agent is intended to help users explore a bounded local corpus of scientific papers. It supports research discovery by extracting structured statements, building a local knowledge graph, discovering gaps, generating speculative hypotheses, drafting experiment plans, and evaluating outputs.

## Users

- Students mapping a research area.
- Researchers comparing a focused set of papers.
- Reviewers looking for limitations and follow-up experiments.
- Public-interest teams exploring scientific evidence responsibly.

## Non-Goals

- Large-scale literature search.
- Cloud deployment.
- Medical, legal, policy, or financial advice.
- Treating generated hypotheses as established discoveries.
- Ingesting private or unlicensed papers without permission.
- Model training or fine-tuning inside the deterministic local baseline.

## Data

The reference demo supports 5-10 local PDFs in `data/papers/`, with the UI capped at 10 PDFs to preserve reviewability and demo speed. Papers should be synthetic, sample, open-access, or otherwise permitted for local processing. The local manifest `data/papers/manifest.json` records filenames and license/source notes.

Processed data is stored locally:

- SQLite database: `data/processed/papers.sqlite`
- GraphML graph: `data/processed/research_graph.graphml`
- Discovery outputs: `data/processed/gaps_and_hypotheses.json`
- Evaluation report: `data/processed/evaluation_report.json`

## Methods

The deterministic local baseline uses:

- Google ADK-facing agent wrapper in `app/agent.py`.
- ADK-compatible local tool functions in `app/adk_tools.py`.
- Local MCP server wrapper in `app/mcp_server.py`.
- PDF extraction with local PDF tools.
- Rule-based statement extraction.
- Deterministic deduplication and filtering.
- Pydantic schemas for core data contracts.
- SQLite storage.
- NetworkX graph construction.
- Rule-based gap discovery and hypothesis generation.
- Deterministic safety and evaluation metrics.
- Streamlit local UI.

## Agent Technology

ResearchNavigator exposes the deterministic backend as an ADK-facing agent. The wrapper registers local function tools for ingestion, graph construction, gap discovery, evaluation, search, evidence inspection, policy checking, project summarization, report generation, capability description, and planned tool trajectory.

The current local baseline intentionally avoids LLM calls during tests and deterministic pipeline runs. The agent story is therefore about reliable tool orchestration, instruction boundaries, grounded retrieval, local policy checks, and evaluation. The Streamlit `Pipeline Trace` tab shows the ADK agent view, callable tool manifest, planned tool trajectory, and per-stage safety gates.

The local MCP wrapper exposes selected deterministic tools to MCP-compatible clients while preserving the same local-first safety boundaries.

## Safety Controls

- Paper text is treated as untrusted content.
- Prompt-injection phrases are flagged.
- Overclaiming phrases are flagged.
- Hypotheses must use the `speculative_research_hypothesis` label.
- Gaps and hypotheses must reference local evidence statement IDs.
- Policy checks block external-send, deployment, training, fine-tuning, external search, and write-outside-workspace actions in the local baseline.
- Future training, fine-tuning, or broader retrieval would require explicit policy changes, new evaluation cases, and human review before use.
- Sensitive context such as email addresses, API keys, private URLs, and local home paths can be detected and sanitized.

## Evaluation

Evaluation reports include:

- overall score
- grounding score
- safety score
- testability score
- traceability score
- warnings
- failed checks
- metric details

Golden cases test extraction, safety, grounding, graph correctness, and gap/hypothesis/plan generation.

## Current Results

```text
Golden cases: 5/5 passed
Submission validator: Ready
Tests: 195 passed
```

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Noisy extraction | Deduplication, filtering, statement caps, quality scoring |
| Fake citations | Local-corpus-only citation policy and evidence IDs |
| Prompt injection in papers | Injection detection and instruction isolation |
| Overclaiming | Speculative labels and overclaiming checks |
| Graph explosion | Statement filtering and graph-size checks |
| Weak evidence diversity | Evaluation warnings and metric details |
| Unlicensed papers | Paper manifest and open-access/synthetic constraint |

## Limitations

The local baseline is deterministic and intentionally bounded. It does not perform semantic extraction, full citation parsing, large-scale retrieval, model training, fine-tuning, or LLM-based reasoning. These boundaries are documented so users understand the review scope.

## Human Oversight

Users should review extracted statements, gaps, hypotheses, and experiment plans before using them in reports or research decisions.
