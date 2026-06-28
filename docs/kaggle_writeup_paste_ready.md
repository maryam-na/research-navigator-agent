# ResearchNavigator Agent: Local, Grounded AI Research Discovery

## Subtitle

A Google ADK-facing research assistant that turns a small local paper collection into evidence-backed research gaps, speculative hypotheses, experiment plans, and safety/evaluation reports.

## Track

Agents for Good

## Writeup

ResearchNavigator Agent is a local-first AI research-discovery assistant for small scientific paper collections. It helps researchers, students, reviewers, and public-interest teams move from a folder of papers to structured evidence, a local knowledge graph, candidate research gaps, speculative hypotheses, experiment plans, and safety/evaluation reports.

The project is designed for the **Agents for Good** track because it addresses a real problem in responsible knowledge work: people increasingly use AI to understand research, but research support tools should not silently invent evidence, overstate findings, or blur the line between what a paper actually says and what a model imagines. ResearchNavigator takes a more cautious path. Every gap and hypothesis is grounded in local evidence statements, every hypothesis is labeled speculative, and the system makes its safety warnings visible instead of hiding them behind a polished answer.

### Why This Problem Matters

Reading scientific papers is slow, especially when the goal is not just to summarize one paper but to compare a small collection. A reviewer or student may need to answer questions like: What methods are being used? What datasets appear repeatedly? What limitations are acknowledged? Which results are connected to those limitations? What future work is suggested? What experiments would be reasonable next steps?

These questions are valuable, but they are also easy to mishandle with generic AI summarization. A normal chatbot can produce a fluent answer, yet the user may not know which paper supports which claim. It may also generate citations that look plausible but are not present in the corpus. In research contexts, this is a serious problem. A useful agent should not merely sound confident; it should preserve evidence trails, separate facts from hypotheses, and make uncertainty visible.

ResearchNavigator is built around that principle. It does not try to be a broad literature search engine. Instead, it focuses on a smaller, more trustworthy workflow: take five to ten local papers, extract structured research statements, connect them in a local graph, identify evidence-backed gaps, generate cautious hypotheses, and show the source evidence behind each output.

### Solution Overview

The system runs fully locally. The MVP uses five local papers in `data/papers/` and stores all generated artifacts in `data/processed/`. The pipeline is deterministic and reproducible:

1. Extract text from local PDFs.
2. Chunk the text into manageable local passages.
3. Extract structured statements such as methods, results, datasets, limitations, future work, and background.
4. Deduplicate and filter noisy statements.
5. Store papers, chunks, and statements in SQLite.
6. Build a local NetworkX research graph.
7. Discover research gaps from limitations, future-work statements, and result/limitation relationships.
8. Generate speculative hypotheses and experiment plans.
9. Evaluate grounding, safety, testability, and traceability.
10. Present the workflow in a Streamlit dashboard.

The dashboard is designed as a research-discovery workspace, not just a set of raw tables. It includes search across the local corpus, an evidence inspector, ranked discoveries, research themes, a graph preview, a report exporter, safety/evaluation metrics, and a pipeline trace. The UI is intentionally local-first and transparent: users can see what was extracted, where it came from, how it connects to gaps and hypotheses, and what warnings remain.

### Agent Technology And ADK Use

ResearchNavigator includes a Google ADK-facing agent wrapper in `app/agent.py`. The wrapper registers deterministic local tools from `app/adk_tools.py`, including tools for ingestion, graph building, gap discovery, evaluation, search, evidence inspection, policy checks, project summarization, report generation, capability description, and planned tool trajectory.

This design demonstrates agent concepts in a controlled, reproducible way. The current MVP intentionally avoids cloud deployment, model training, fine-tuning, and LLM calls during deterministic pipeline execution. That choice is deliberate: for this capstone, I wanted to show that an agent can be valuable not only through open-ended generation, but also through disciplined tool orchestration, safety boundaries, traceable local state, and evaluation.

The Streamlit `Pipeline Trace` tab makes the agent architecture visible. It shows the ADK agent view, the callable tool manifest, the planned deterministic tool trajectory, the safety gate for each stage, and the final answer contract for grounded responses. This is important because judges can inspect not only the final output, but also the agentic workflow that produced it.

The agent’s operating contract is simple: treat paper text as untrusted data, cite local statement IDs, separate extracted evidence from speculative hypotheses, and block actions that do not belong in the local MVP. This turns the agent from a black-box answer generator into a transparent research assistant.

The project also includes a local MCP server wrapper in `app/mcp_server.py`. This exposes selected deterministic tools such as search, evidence inspection, project summary, policy checking, and research brief generation to MCP-compatible clients while preserving the same local-first safety boundaries.

### Course Concepts Demonstrated

The full criterion-by-criterion evidence map is in `docs/capstone_evaluation_mapping.md`.

The project demonstrates several course concepts directly:

- **Agent / ADK:** `app/agent.py` defines the Google ADK-facing agent wrapper, and `app/adk_tools.py` exposes deterministic tools for orchestration.
- **MCP Server:** `app/mcp_server.py` provides a local MCP wrapper around selected ResearchNavigator tools.
- **Security features:** `tools/safety_tools.py`, `tools/policy_tools.py`, and `specs/safety_policy.md` enforce prompt-injection checks, overclaiming checks, policy gates, and evidence grounding.
- **Agent skills:** `SKILL.md` and `.agent/skills/research-navigator/SKILL.md` document reusable project-specific agent behavior.
- **Deployability:** the project is reproducible locally with `make demo`, `make ui`, `make preflight`, and `make mcp`.
- **Antigravity:** the video demonstrates the project being inspected and validated inside Antigravity as the agentic coding environment.

### Documentation Rubric Coverage

This writeup is organized to satisfy the written-submission rubric directly:

- **Problem:** manual comparison of small paper collections is slow, and ungrounded AI
  summaries can overclaim or invent citations.
- **Solution:** a local pipeline builds structured evidence, a graph, ranked gaps,
  speculative hypotheses, experiment plans, and evaluation reports.
- **Architecture:** the README Mermaid diagram, `Pipeline Trace` tab,
  `docs/system_card.md`, and `docs/agent_technology_story.md` describe the flow from
  local PDFs to Streamlit.
- **Setup:** `README.md`, `SUBMISSION.md`, `docs/reproducibility.md`, and
  `docs/judge_walkthrough.md` provide local run commands.
- **Images and demo artifacts:** `docs/screenshots/` and `docs/sample_outputs/`
  provide the gallery and output excerpts.
- **Project journey:** the limitations and next-steps sections explain what is
  implemented, what is intentionally local-only, and what still needs human review.

### Knowledge Graph And Discovery Workflow

The knowledge graph is built with NetworkX from extracted statements. Papers connect to statements, and typed statement nodes represent methods, results, limitations, future-work items, datasets, background, and unknown statements. Semantic edges connect methods to results, results to limitations, limitations to future work, and datasets to methods when they occur in the same paper.

This graph gives the system a structured way to reason about research opportunities. A limitation can become a candidate gap. A future-work statement can become a candidate gap. A result connected to a limitation can also suggest a gap worth testing. From these gaps, the system generates cautious hypotheses and experiment plans. Each hypothesis references evidence statement IDs and uses the safety label `speculative_research_hypothesis`.

The goal is not to claim discovery. The goal is to help a human researcher notice promising directions while keeping the evidence trail intact.

### Safety, Grounding, And Policy Controls

The safety layer is central to the project. Paper text is treated as untrusted input, not as instructions. The system detects prompt-injection phrases such as "ignore previous instructions," "system prompt," and "developer message." It also checks for overclaiming phrases such as "proves," "guarantees," and "definitively shows."

Grounding checks verify that outputs reference existing local evidence statement IDs. Unsupported hypotheses fail safety. Hypotheses must be explicitly speculative. The project also includes local policy checks for actions that should not happen in this MVP, including external email, deployment, model training, fine-tuning, external search, and writing outside the workspace.

This matters because scientific tools should not only produce impressive outputs; they should also make it harder to misuse those outputs. ResearchNavigator shows warnings when evidence is narrow or plans are generic, because a responsible system should tell users when its outputs need review.

### Evaluation And Engineering Quality

The project includes deterministic tests, golden evaluation cases, preflight checks, dependency audit, coverage reporting, structured logging, Pydantic schemas, and a submission validator.

Current local results:

```text
Tests: 172 passed
Golden evals: 5/5 passed
Submission validator: ready
Preflight: ready
Coverage: 72.51%
Overall evaluation score: 0.917
Grounding score: 0.78
Safety score: 1.0
Testability score: 0.932
Traceability score: 1.0
```

The project currently has zero failed submission checks. It keeps two honest evaluation
warnings visible: generated gaps and hypotheses draw evidence from one paper or fewer,
and experiment plans are structurally complete but still somewhat generic. I
intentionally keep those warnings visible because it reflects the product philosophy:
a trustworthy research assistant should surface limitations, not bury them.

The codebase is also structured for review. Core data contracts are defined with Pydantic schemas. SQLite stores papers, chunks, and statements. NetworkX manages graph construction. Streamlit provides the local dashboard. Pytest covers deterministic behavior. The preflight script checks local readiness, the dependency audit checks lock coverage and local-first dependency risk, and the coverage report makes test coverage visible.

### User Experience

The dashboard is meant to feel like a professional research discovery tool. The top-level view shows corpus statistics, graph size, grounding score, and safety status. The Search tab lets users ask questions over papers, statements, gaps, hypotheses, and experiment plans. The Evidence Inspector lets users inspect a source statement, its evidence snippet, quality signals, and linked discoveries. The Discoveries tab ranks gaps and shows linked hypotheses and plans. The Knowledge Graph tab provides a visual graph preview. The Safety & Evaluation tab shows scores, warnings, and failed checks. The Pipeline Trace tab makes the ADK-facing agent architecture visible.

This user experience is important because research discovery is not just about output generation. It is about helping users understand why an output exists, what evidence supports it, and what still requires human judgment.

### Impact

ResearchNavigator can help students map a research area, help reviewers inspect limitations and follow-up ideas, and help public-interest teams explore scientific claims more responsibly. It is especially useful when users have a small trusted corpus and want structured insight without sending papers to a cloud service.

The project’s value is not that it replaces researchers. It helps them move faster while preserving caution. It turns scattered paper text into a grounded workspace for exploration, and it keeps the human in charge of interpretation.

### Limitations And Next Steps

The MVP is intentionally narrow. Statement extraction is rule-based rather than semantic. It does not perform large-scale literature search, full citation parsing, or page-level PDF citation grounding. The ADK wrapper is currently local and prototype-focused. Experiment plans are useful as structured starting points, but they still need human refinement.

Future work would include richer ADK trajectory evaluation, optional human-in-the-loop review gates, semantic retrieval over local chunks, stronger citation metadata, domain-specific experiment-plan templates, and better evidence diversity across papers.

### Why This Project Is Competition-Ready

ResearchNavigator demonstrates a practical agent workflow with a clear social-good use case, thoughtful architecture, local-first constraints, grounded outputs, visible ADK tool orchestration, safety controls, evaluation metrics, and a polished dashboard. It is not only a chatbot interface; it is a reproducible research-discovery system with evidence, policy, graph structure, and evaluation built into the experience.
