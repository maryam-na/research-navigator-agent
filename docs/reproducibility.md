# Reproducibility Guide

This guide describes how to reproduce the local ResearchNavigator Agent demo.

## Requirements

- Python 3.11 or newer
- `uv`
- local repository checkout
- 5-10 local PDFs in `data/papers/`

## Install

```bash
uv sync --extra dev
```

## Run The Demo

```bash
make demo
```

Default paths and thresholds are configured in:

```text
configs/default.yaml
```

Expected output includes:

```text
ResearchNavigator demo complete.
Papers: 5
Statements: 395 saved from 7228 raw
Graph: 795 nodes, 1052 edges
Gaps: 10
Hypotheses: 10
Overall score: 0.917
Failed checks: 0
```

Exact counts may change if the paper set changes.

## Run Golden Evaluations

```bash
make eval
```

Expected output:

```text
Golden cases: 5/5 passed
Pass rate: 1.0
Failed cases: 0
```

## Validate Submission Readiness

```bash
make validate
```

Expected output:

```text
Ready: True
Failed: 0
```

Warnings may be present when evaluation caveats need review.

## Run Tests

```bash
make test
```

Expected output:

```text
114 passed
```

ADK dependency warnings may appear during import; they are not test failures.

## Launch UI

```bash
make ui
```

Then open:

```text
http://localhost:8501
```

## Regenerate Sample Outputs

```bash
make samples
```

This writes compact excerpts to:

```text
docs/sample_outputs/
```

## Important Generated Files

```text
data/processed/papers.sqlite
data/processed/research_graph.graphml
data/processed/gaps_and_hypotheses.json
data/processed/evaluation_report.json
data/processed/golden_eval_report.json
data/processed/submission_validation_report.json
data/processed/researchnavigator_brief.md
```

## Troubleshooting

If ingestion finds zero papers, check that PDFs exist in `data/papers/`.

If graph export fails, rerun:

```bash
make demo
```

If validation fails because sample outputs or screenshots are missing, run:

```bash
make samples
make validate
```

If dependencies are missing, run:

```bash
uv sync --extra dev
```
