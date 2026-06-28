# Judge Walkthrough

Use this path to review ResearchNavigator Agent in about five minutes.

## 1. Read The Submission Summary

Open:

```text
SUBMISSION.md
docs/capstone_evaluation_mapping.md
```

This explains the problem, solution, safety approach, key results, and
criterion-by-criterion evidence map.

## 2. Run The Local Demo

```bash
make demo
```

This runs ingestion, statement extraction, graph building, gap discovery, hypothesis generation, experiment planning, evaluation, and brief generation.

## 3. Run Golden Evaluations

```bash
make eval
```

Expected:

```text
Golden cases: 5/5 passed
```

## 4. Validate Submission Readiness

```bash
make validate
```

Expected:

```text
Ready: True
Failed: 0
```

## 5. Inspect The Agent Technology Story

Open:

```text
app/agent.py
app/adk_tools.py
```

Then open the Streamlit `Pipeline Trace` tab. Review:

- ADK agent view
- callable local tool manifest
- planned deterministic tool trajectory
- per-stage safety gates
- final answer contract for grounded responses

This shows how the MVP applies agent concepts without cloud deployment or LLM calls in the deterministic pipeline.

## 6. Inspect Screenshots And Sample Outputs

Screenshots:

```text
docs/screenshots/
```

Sample outputs:

```text
docs/sample_outputs/
```

## 7. Open The Dashboard

```bash
make ui
```

Review these tabs:

- Search
- Evidence Inspector
- Discoveries
- Research Themes
- Knowledge Graph
- Safety & Evaluation
- Pipeline Trace

## 8. Review Safety And Limitations

Open:

```text
docs/system_card.md
docs/reproducibility.md
specs/safety_policy.md
```

Confirm that generated hypotheses are speculative and grounded in local evidence IDs.
