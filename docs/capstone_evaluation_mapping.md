# Capstone Evaluation Mapping

This audit maps the Kaggle capstone criteria to concrete ResearchNavigator Agent evidence.
It is intentionally conservative: it only claims capabilities that are visible in code,
documentation, local commands, or the planned video.

## Summary

ResearchNavigator demonstrates more than the required three course concepts:

- Agent / ADK system: code evidence in `app/agent.py` and `app/adk_tools.py`.
- MCP server: code evidence in `app/mcp_server.py` and `scripts/run_mcp_server.py`.
- Security features: code evidence in `tools/safety_tools.py`, `tools/policy_tools.py`,
  `tools/evaluation_tools.py`, and `specs/policies.yaml`.
- Agent skills: code/documentation evidence in `SKILL.md` and
  `.agent/skills/research-navigator/SKILL.md`.
- Deployability/reproducibility: documentation and video evidence through `Makefile`,
  `docs/reproducibility.md`, `scripts/preflight.py`, and `scripts/validate_submission.py`.
- Antigravity: video-only evidence through `docs/antigravity_demo_notes.md` and
  `docs/kaggle_video_scenario_4min.md`.

No blocking rubric gaps were found. Remaining proof work is presentation polish: record the
Antigravity segment, show local commands in the video, and keep the final README/writeup aligned
with the actual local-first MVP. Those follow-ups are tracked in the local ticket plan.

## Key Concept Evidence

- Agent / Multi-agent system (ADK)
  - Required: Code.
  - Evidence: `app/agent.py`, `app/adk_tools.py`, Pipeline Trace tab, and
    `docs/agent_technology_story.md`.
  - Status: Strong.
  - Notes: `root_agent` registers deterministic tools. The app exposes the tool
    manifest, planned trajectory, safety gates, and final answer contract.

- MCP Server
  - Required: Code.
  - Evidence: `app/mcp_server.py`, `scripts/run_mcp_server.py`, `docs/mcp_server.md`,
    and `Makefile` target `mcp`.
  - Status: Strong.
  - Notes: Local MCP wrapper exposes search, evidence inspection, summary, policy,
    trajectory, and brief-generation tools.

- Antigravity
  - Required: Video.
  - Evidence: `docs/antigravity_demo_notes.md`, `docs/kaggle_video_script.md`, and
    `docs/kaggle_video_scenario_4min.md`.
  - Status: Video required.
  - Notes: Must be shown in the final recording. Do not claim this as code evidence.

- Security features
  - Required: Code or video.
  - Evidence: `tools/safety_tools.py`, `tools/policy_tools.py`,
    `tools/evaluation_tools.py`, `specs/safety_policy.md`, and
    `docs/security_review.md`.
  - Status: Strong.
  - Notes: Covers prompt-injection phrases, overclaiming, grounding, policy blocks,
    sensitive-context sanitization, and evaluation warnings.

- Deployability
  - Required: Video.
  - Evidence: `Makefile`, `docs/reproducibility.md`, `docs/judge_walkthrough.md`,
    `scripts/preflight.py`, and `scripts/validate_submission.py`.
  - Status: Strong local reproducibility.
  - Notes: The project is not publicly deployed by design. Show `make demo`,
    `make ui`, `make validate`, or `make preflight` in the video.

- Agent skills
  - Required: Code or video.
  - Evidence: `SKILL.md`, `.agent/skills/research-navigator/SKILL.md`, and
    `AGENTS.md`.
  - Status: Strong.
  - Notes: Skill docs define local workflow, constraints, tool map, safety rules,
    and evaluation focus.

## Category 1: Pitch, Problem, Solution, Value

- Core concept and value
  - Evidence: `README.md`, `SUBMISSION.md`, `docs/kaggle_submission_package.md`,
    and `docs/kaggle_video_script.md`.
  - Status: Ready.
  - Notes: Pitch is local, grounded research discovery for 5-10 papers.

- Meaningful use of agents
  - Evidence: `app/agent.py`, `app/adk_tools.py`, `docs/agent_technology_story.md`,
    and the Pipeline Trace tab.
  - Status: Ready.
  - Notes: Agent value is tool orchestration, policy boundaries, grounded retrieval,
    evidence inspection, and safety/evaluation checks.

- Problem statement
  - Evidence: `SUBMISSION.md`, `docs/kaggle_submission_package.md`, and
    `docs/kaggle_video_script.md`.
  - Status: Ready.
  - Notes: Problem is slow manual research comparison plus ungrounded AI summaries.

- YouTube video clarity
  - Evidence: `docs/kaggle_video_script.md`, `docs/kaggle_video_scenario_4min.md`,
    and `docs/antigravity_demo_notes.md`.
  - Status: Ready for recording.
  - Notes: Script covers problem, agents, architecture, demo, build, MCP, safety,
    Antigravity, and local commands.

- Architecture visuals
  - Evidence: `README.md` Mermaid diagram, `docs/screenshots/`, and Pipeline Trace.
  - Status: Ready.
  - Notes: Covers pipeline, graph, evidence, safety, and dashboard flow.

- Demo
  - Evidence: `docs/judge_walkthrough.md`, `docs/kaggle_video_scenario_4min.md`,
    `docs/screenshots/`, and `docs/sample_outputs/`.
  - Status: Ready.
  - Notes: Demo path shows Search, Evidence Inspector, Discoveries, Knowledge Graph,
    Safety & Evaluation, and Pipeline Trace.

- Written submission
  - Evidence: `SUBMISSION.md`, `docs/kaggle_submission_package.md`, and `README.md`.
  - Status: Ready.
  - Notes: Writeup covers problem, solution, architecture, safety, evaluation,
    limitations, and run commands.

## Category 2: Implementation, Architecture, Code

- Technical implementation
  - Evidence: `tools/`, `scripts/`, `ui/streamlit_app.py`, `app/adk_tools.py`,
    and `app/mcp_server.py`.
  - Status: Ready.
  - Notes: Covers ingestion, extraction, storage, graph, discovery, evaluation, UI,
    ADK-facing tools, and MCP wrapper.

- Architecture quality
  - Evidence: `README.md`, `docs/system_card.md`, `docs/agent_technology_story.md`,
    and `specs/project_spec.md`.
  - Status: Ready.
  - Notes: Architecture is local PDFs to extraction, SQLite, NetworkX, discovery,
    safety/evaluation, and Streamlit.

- Meaningful AI/agent integration
  - Evidence: `app/agent.py`, `app/adk_tools.py`, and Pipeline Trace tab.
  - Status: Ready.
  - Notes: Agent wrapper is explicit and local-first. The deterministic MVP does not
    use LLM calls during tests or pipeline execution.

- Tool use
  - Evidence: `app/adk_tools.py`, `tools/*`, `scripts/*`, and `Makefile`.
  - Status: Ready.
  - Notes: Toolset includes local PDF parsing, SQLite, NetworkX, safety/policy
    checks, evaluations, sample-output generation, validation, and MCP.

- Comments and readable code
  - Evidence: `app/`, `tools/`, `scripts/`, and `ui/`.
  - Status: Ready.
  - Notes: Code uses focused docstrings and comments where behavior matters.

- No secrets
  - Evidence: `docs/security_review.md`, `scripts/dependency_audit.py`, and
    `specs/policies.yaml`.
  - Status: Ready.
  - Notes: No API keys are required. Local policy blocks external deployment,
    email, training, fine-tuning, browsing, and write-outside-workspace actions.

- Reproducibility
  - Evidence: `Makefile`, `docs/reproducibility.md`, and `docs/judge_walkthrough.md`.
  - Status: Ready.
  - Notes: Local commands reproduce demo, evals, validation, UI, brief generation,
    preflight, and MCP.

- Documentation
  - Evidence: `README.md`, `SUBMISSION.md`, `docs/kaggle_submission_package.md`,
    `docs/system_card.md`, and `docs/security_review.md`.
  - Status: Ready.
  - Notes: README includes problem, architecture, setup/run commands, screenshots,
    ADK/MCP notes, and known limitations.

## Safety And Honesty Checks

- Do not claim public cloud deployment. The deployability evidence is local reproducibility.
- Do not claim Antigravity is demonstrated by code. It must be shown in the video.
- Do not claim the MVP performs LLM reasoning during deterministic tests or pipeline runs.
- Do not claim hypotheses are discoveries. They are speculative and evidence-linked.
- Do not claim citation completeness beyond local statement IDs and available paper metadata.
- Keep evaluation warnings visible: evidence diversity and generic experiment plans still
  need review.

## Final Readiness Checklist

- `make demo`: regenerates local processed artifacts.
- `make eval`: runs deterministic golden cases.
- `make validate`: checks required docs, artifacts, screenshots, sample outputs,
  corpus, and metrics.
- `make ui`: launches the dashboard for live demo.
- `make mcp`: launches the local MCP server wrapper.
- Video should show: problem, dashboard demo, Pipeline Trace ADK view, MCP manifest,
  Safety & Evaluation, Antigravity, and at least one local validation command.

## Follow-up Proof Items

These are not blocking code gaps, but they should be completed before final submission:

- Record the Antigravity segment described in `docs/antigravity_demo_notes.md`.
- Keep the final video under five minutes while showing ADK, MCP, safety, and local commands.
- Re-run `make validate` after refreshing screenshots or sample outputs.
- Keep README and writeup numbers synchronized with the latest validation/test run.
