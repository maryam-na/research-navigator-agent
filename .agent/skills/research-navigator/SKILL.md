# ResearchNavigator Agent

Use this skill to work on ResearchNavigator Agent, a local-first research-discovery assistant for bounded scientific literature collections.

## Trigger

Use this skill when the task involves:

- ingesting local papers
- extracting research statements
- building a local knowledge graph
- finding research gaps
- generating speculative hypotheses
- drafting experiment plans
- checking grounding, safety, or evaluation behavior
- improving the Streamlit research dashboard
- strengthening ADK/MCP agent concept visibility

## Required Context

Read these files before implementation work:

- `SKILL.md`
- `AGENTS.md`
- `specs/project_spec.md`
- `specs/safety_policy.md`
- `specs/evaluation_plan.md`
- `specs/behavior_scenarios.md`
- `specs/policies.yaml`

## Workflow

1. Inspect current specs and tests.
2. Make a focused deterministic change that satisfies the requested behavior.
3. Keep evidence IDs attached to research outputs.
4. Run safety and policy checks where relevant.
5. Run pytest.
6. Update docs if behavior changes.

## Agent Concept Proof Points

- `app/agent.py`: ADK-facing root agent instruction and tool registration.
- `app/adk_tools.py`: deterministic tools, capability manifest, tool trajectory,
  policy boundaries, and final-answer contract.
- `app/mcp_server.py`: local MCP wrapper exposing selected tools with safety metadata.
- `ui/streamlit_app.py`: Pipeline Trace tab showing ADK, MCP, tool trajectory, safety
  gates, human-review gates, and local commands.
- `SKILL.md`: reusable local-first behavior contract for future agent work.

## Commands

```bash
uv run --extra dev pytest
uv run python -m scripts.ingest_papers --papers-dir data/papers --db-path data/processed/papers.sqlite --extract-statements --filter-statements --max-statements-per-type-per-paper 30
uv run python -m scripts.build_graph --db-path data/processed/papers.sqlite --graph-path data/processed/research_graph.graphml
uv run python -m scripts.discover_gaps --db-path data/processed/papers.sqlite --output-path data/processed/gaps_and_hypotheses.json
uv run python -m scripts.evaluate_outputs --db-path data/processed/papers.sqlite --input-path data/processed/gaps_and_hypotheses.json --output-path data/processed/evaluation_report.json
uv run streamlit run ui/streamlit_app.py
```

## Guardrails

- Keep external sends, deployment, model-changing workflows, and unrestricted web actions behind policy review.
- Do not silently accept missing evidence.
- Do not present hypotheses as proven findings.
- Do not expand beyond the 5-10 paper reference-demo scope unless the user explicitly changes it.
