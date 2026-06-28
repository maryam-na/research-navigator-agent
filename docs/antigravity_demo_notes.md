# Antigravity Demo Notes

Antigravity is demonstrated in the video, not as a code artifact. Keep this segment
short, concrete, and honest.

## Segment Goal

Show that the project was inspected and validated inside Antigravity as the agentic
coding environment. The codebase itself demonstrates ADK, MCP, security features,
agent skills, and local reproducibility. Antigravity is the build/review environment
shown in the recording.

## 15-25 Second Shot List

1. Open the ResearchNavigator project folder in Antigravity.
2. Show at least one agent-facing file:
   - `app/agent.py`
   - `app/adk_tools.py`
   - `app/mcp_server.py`
   - `SKILL.md`
3. Show a local terminal result from one command:

```bash
make preflight
```

or:

```bash
make validate
```

4. Return to the Streamlit dashboard or Pipeline Trace for the closing.

## Suggested Line

Say:

> I used Antigravity as the agentic coding environment to inspect the codebase, run
> local validation commands, and iterate on the ADK/MCP wrapper and Streamlit demo.

Only say this if Antigravity is visible in the recording.

## Claim Guardrails

- Do not say Antigravity is a deployed component of the app.
- Do not say Antigravity is code evidence for ADK or MCP.
- Do not show API keys, private files, or unrelated workspaces.
- Do not show a failing command unless explaining it as a development step.
- Prefer `make preflight` or `make validate` because they are quick and judge-relevant.
