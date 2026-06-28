# Changelog

## 0.1.0

Initial competition-ready local MVP.

### Added

- Local PDF ingestion and deterministic chunking.
- SQLite storage for papers, chunks, and statements.
- Rule-based statement extraction, filtering, and deduplication.
- NetworkX research graph construction and GraphML export.
- Deterministic gap discovery, hypothesis generation, and experiment planning.
- Safety checks for prompt injection, overclaiming, hypothesis labels, and evidence grounding.
- Evaluation metrics with warnings and failed checks.
- Local Streamlit dashboard.
- Search-first UI, evidence inspector, ranked gaps, research themes, graph preview, report export, and pipeline trace.
- Policy checks for blocked tools and sensitive context.
- Root `SKILL.md`, `AGENTS.md`, and `.agent/skills/research-navigator/SKILL.md`.
- Lightweight ADK-facing wrapper in `app/agent.py` and `app/adk_tools.py`.
- One-command demo pipeline.
- Deterministic golden evaluation runner.
- Submission validator.
- Demo screenshots and sample output gallery.
- Judge-facing submission summary, system card, reproducibility guide, and walkthrough.
- Structured local logging helpers for demo and validation scripts.
- Pydantic schemas for core pipeline records and reports.
- Local preflight script for dependency, config, artifact, schema, and graph-size checks before demos.
- Offline dependency audit for lock coverage, direct usage, local-first risk, and dependency footprint.
- Local pytest coverage report with JSON and Markdown outputs.
- Local MCP server wrapper in `app/mcp_server.py` and `scripts/run_mcp_server.py`.
- Antigravity video demonstration notes for showing the agentic coding workflow.

### Current Validation

- Tests: maintained by `make ci`.
- Golden evals: 5/5 passed.
- Preflight: ready.
- Dependency audit: local/offline.
- Coverage report: local pytest-cov.
- Submission validator: ready with zero failed checks.
