# Local MCP Server

ResearchNavigator includes a local Model Context Protocol server wrapper around selected deterministic tools.

Run:

```bash
make mcp
```

or:

```bash
uv run python -m scripts.run_mcp_server
```

Server module:

```text
app/mcp_server.py
```

The MCP server exposes:

- `describe_agent_capabilities`
- `planned_tool_trajectory`
- `summarize_local_project`
- `search_local_corpus`
- `inspect_evidence`
- `generate_local_research_brief`
- `check_local_policy`

The manifest also includes each tool's stage and safety gate so MCP clients can see
that the exposed capabilities follow the same local-first boundaries as the ADK layer.

## Why It Exists

The ADK wrapper demonstrates agent orchestration inside the project. The MCP wrapper demonstrates how the same local deterministic capabilities can be exposed to an MCP-compatible client without changing the safety model.

The server remains local-first:

- It reads local processed artifacts.
- It does not deploy a public endpoint.
- It does not make LLM calls.
- It keeps policy checks available as a callable tool.

## Suggested Demo

In the demo walkthrough, briefly show:

```bash
uv run python -c "from app.mcp_server import mcp_tool_manifest; print(mcp_tool_manifest())"
```

Then explain that `make mcp` launches the local MCP server for MCP-compatible clients.
