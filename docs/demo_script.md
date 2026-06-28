# ResearchNavigator Agent Demo Script

Use this as a two-minute walkthrough for reviewers or competition judges.

## 0:00 - Problem

Researchers often read small paper collections manually and lose track of methods, datasets, results, limitations, and follow-up opportunities. ResearchNavigator Agent helps map a small local corpus into evidence-backed discoveries without sending papers to the cloud.

## 0:20 - Local Pipeline

Show the one-command demo:

```bash
uv run python -m scripts.run_demo --reset
```

Explain that the command ingests local PDFs, chunks text, extracts structured statements, builds a NetworkX graph, discovers gaps, generates cautious hypotheses, drafts experiment plans, and evaluates outputs.

## 0:45 - Search-First UI

Open:

```bash
uv run streamlit run ui/streamlit_app.py
```

Search for:

```text
limitations evaluation dataset
```

Point out that results include evidence IDs and source snippets.

## 1:05 - Evidence Inspector

Open the Evidence Inspector tab. Show one limitation statement and explain:

- statement type
- source paper
- chunk ID
- evidence snippet
- quality signals
- linked gaps and hypotheses

## 1:25 - Research Gaps And Hypotheses

Open Discoveries. Show ranked gaps, linked evidence, speculative hypotheses, and experiment plans. Emphasize that hypotheses are not presented as proven discoveries.

## 1:40 - Safety And Evaluation

Open Safety & Evaluation. Explain:

- grounding score
- safety score
- testability score
- traceability score
- warnings
- failed checks

Clarify that warnings make the score honest when evidence is narrow or plans are generic.

## 1:55 - Why It Matters

Close with the value:

ResearchNavigator Agent is local-first, evidence-backed, policy-gated, and evaluated. It is designed for responsible research discovery over a small corpus, not broad ungrounded literature search.
