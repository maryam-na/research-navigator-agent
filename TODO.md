# TODO: 14-Day Implementation Plan

## Day 1: Project Contracts

- Choose SQLite or DuckDB for the MVP storage layer.
- Define Pydantic schemas for papers, passages, claims, methods, datasets, results, limitations, future work, gaps, hypotheses, and experiment plans.
- Convert `evals/golden_cases.json` into a tracked baseline for future ADK evals.

## Day 2: Local Paper Fixtures

- Add 2-3 synthetic/sample paper fixtures under `data/samples/`.
- Define the accepted paper metadata format.
- Add license/source notes for any open-access papers.

## Day 3: Parsing Layer

- Implement deterministic local paper parsing for text fixtures first.
- Add PDF parsing only after text fixtures are stable.
- Write pytest tests for parser contracts and metadata handling.

## Day 4: Storage Layer

- Implement SQLite or DuckDB tables for papers, passages, extracted records, and safety labels.
- Add migrations or schema initialization.
- Write pytest tests for inserts, reads, and duplicate handling.

## Day 5: Extraction Schemas and Tool Stub

- Create ADK tool stubs for research-unit extraction.
- Enforce structured output through Pydantic validation.
- Add tests for schema validation and malformed extraction records.

## Day 6: Safety Helpers

- Implement prompt-injection pattern checks.
- Implement fake-citation and missing-citation checks.
- Implement overclaiming label helpers.
- Add pytest coverage for all safety helpers.

## Day 7: Knowledge Graph Builder

- Implement NetworkX graph construction from stored records.
- Add typed nodes and directed edges from `specs/project_spec.md`.
- Add tests for expected node and edge creation.

## Day 8: Graph Query Tools

- Add graph query helpers for methods, datasets, limitations, future work, and gaps.
- Add deterministic tests for graph query outputs.
- Decide whether graph artifacts are persisted or rebuilt from storage.

## Day 9: ADK Agent Orchestration

- Wire ADK tools into the initial agent workflow.
- Enforce safety checks before storage and before generation.
- Run a local smoke test with a synthetic fixture.

## Day 10: Gap and Hypothesis Generation

- Implement grounded gap-analysis tool.
- Implement hypothesis-generation tool with speculative labels.
- Add safety checks for unsupported gaps and overclaiming.

## Day 11: Experiment Planner

- Implement experiment-plan drafting with controls, metrics, evidence requirements, and risks.
- Require linked gap and hypothesis ids.
- Add safety checks for unsupported experiment claims.

## Day 12: Streamlit Dashboard Skeleton

- Add Streamlit views for corpus, extractions, safety flags, graph summary, gaps, hypotheses, and experiment plans.
- Keep UI local-only and read from local storage.
- Avoid adding alternate UI frameworks.

## Day 13: Evaluation Harness

- Convert golden cases into ADK evaluation format.
- Add evaluation checks for extraction quality, grounding, graph correctness, safety, and tool trajectory.
- Run the first eval baseline and record gaps.

## Day 14: MVP Hardening

- Fix the highest-risk eval failures.
- Add README usage instructions for local setup.
- Add a final MVP checklist for corpus licensing, grounding, safety labels, and tests.
- Prepare a demo script using only synthetic/sample or open-access papers.

