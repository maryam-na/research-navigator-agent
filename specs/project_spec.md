# Project Spec

## Project Name

ResearchNavigator Agent

## Track

Agents for Good

## Overview

ResearchNavigator Agent is a secure and evaluated AI research-discovery assistant. It helps users inspect a small local corpus of scientific papers, extract structured research knowledge, build a local knowledge graph, identify research gaps, propose testable hypotheses, and generate experiment plans grounded in the papers.

The first version is intentionally narrow: a local-first prototype over 5-10 synthetic/sample or open-access papers. It will not train models, fine-tune models, deploy to cloud services, or ingest arbitrary web content.

## Target Users

- Students learning to map a research area.
- Researchers comparing a small set of papers.
- Reviewers looking for limitations, missing experiments, and possible follow-up studies.
- Nonprofit or public-interest teams exploring scientific literature with careful grounding.

## Core Workflow

1. User adds 5-10 local papers to the project.
2. Ingestion tool parses text and metadata from each paper.
3. Extraction tool identifies:
   - claims
   - methods
   - datasets
   - results
   - limitations
   - future-work statements
4. Storage tool writes structured records to SQLite or DuckDB.
5. Graph tool builds a NetworkX knowledge graph with typed nodes and edges.
6. Gap-analysis tool finds underexplored methods, datasets, assumptions, limitations, contradictions, or missing validation.
7. Hypothesis tool proposes testable, bounded hypotheses.
8. Experiment-planning tool drafts experiment plans with controls, expected evidence, risks, and required datasets.
9. Safety tools check prompt injection, unsupported claims, fake citations, and overclaiming.
10. Streamlit dashboard displays extracted records, graph summaries, gaps, hypotheses, experiment plans, and evaluation results.

## Planned Architecture

```text
Local papers
    ↓
Paper parser
    ↓
Structured extraction
    ↓
Grounding and safety checks
    ↓
SQLite or DuckDB storage
    ↓
NetworkX knowledge graph
    ↓
Gap analysis, hypothesis generation, experiment planning
    ↓
Streamlit dashboard
```

## ADK Responsibilities

Google ADK will orchestrate the agent workflow and tool calls. Planned tools:

- `ingest_paper`: Parse a local paper into text chunks and metadata.
- `extract_research_units`: Extract claims, methods, datasets, results, limitations, and future work.
- `store_extraction`: Persist structured records in SQLite or DuckDB.
- `build_knowledge_graph`: Convert stored records into a NetworkX graph.
- `query_graph`: Answer graph-based questions.
- `check_safety`: Detect prompt injection, unsupported claims, fake citations, and overclaiming.
- `find_research_gaps`: Identify bounded gaps grounded in the corpus.
- `propose_hypotheses`: Generate testable hypotheses grounded in extracted gaps.
- `draft_experiment_plan`: Generate experiment plans with evidence requirements and limitations.

## Data Model

Planned core entities:

- `Paper`: title, authors, year, venue, source path, license/source notes.
- `Passage`: paper id, page/section, text span, chunk id.
- `Claim`: normalized statement, source passage ids, confidence, scope.
- `Method`: name, description, source passage ids.
- `Dataset`: name, domain, size if available, source passage ids.
- `Result`: metric/outcome, associated claim/method/dataset, source passage ids.
- `Limitation`: limitation text, affected claim/method/result, source passage ids.
- `FutureWork`: proposed direction, source passage ids.
- `ResearchGap`: gap statement, evidence, missing evidence, source passage ids.
- `Hypothesis`: hypothesis, variables, testability notes, linked gap ids.
- `ExperimentPlan`: design, datasets, controls, metrics, expected evidence, risks.

## Knowledge Graph

The graph will use NetworkX with typed nodes and edges.

Example nodes:

- paper
- passage
- claim
- method
- dataset
- result
- limitation
- future_work
- gap
- hypothesis
- experiment_plan

Example edges:

- `paper_has_passage`
- `passage_supports_claim`
- `claim_uses_method`
- `claim_evaluated_on_dataset`
- `method_produces_result`
- `result_has_limitation`
- `limitation_suggests_gap`
- `future_work_suggests_gap`
- `gap_motivates_hypothesis`
- `hypothesis_tested_by_experiment`

## Success Criteria

- Runs locally from the repository with no cloud deployment.
- Ingests 5-10 local papers.
- Produces structured extraction records with source passage grounding.
- Builds a queryable NetworkX graph.
- Flags unsafe or unsupported content instead of silently using it.
- Generates hypotheses and experiment plans that clearly separate evidence from speculation.
- Includes pytest tests for deterministic code paths.
- Includes evaluation cases for extraction, grounding, graph correctness, safety, and tool trajectory.

## Non-Goals

- Cloud deployment.
- Model training or fine-tuning.
- Large-scale literature search.
- Autonomous web browsing.
- Medical, legal, or policy recommendations.
- Treating generated hypotheses as proven discoveries.
- Accepting unlicensed or copyrighted papers without permission.

## Open Decisions

- Choose SQLite or DuckDB for the first implementation.
- Choose the local paper parsing library and supported file formats.
- Define exact ADK eval format after the initial tool skeleton exists.
- Decide whether graph artifacts are stored as GraphML, JSON, or rebuilt from tables.

