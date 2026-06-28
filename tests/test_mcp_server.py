from app.mcp_server import MCP_SERVER_NAME, create_mcp_server, mcp_tool_manifest, register_mcp_tools


class FakeMCPServer:
    def __init__(self):
        self.tools = {}

    def tool(self, name=None, description=None):
        def decorator(func):
            self.tools[name or func.__name__] = {
                "description": description,
                "func": func,
            }
            return func

        return decorator


def test_mcp_tool_manifest_exposes_expected_tools():
    manifest = mcp_tool_manifest()
    names = {tool["name"] for tool in manifest}

    assert MCP_SERVER_NAME == "research-navigator-agent"
    assert "search_local_corpus" in names
    assert "inspect_evidence" in names
    assert "check_local_policy" in names
    assert "describe_agent_capabilities" in names


def test_register_mcp_tools_registers_fake_server_tools():
    server = FakeMCPServer()

    register_mcp_tools(server)

    assert "planned_tool_trajectory" in server.tools
    assert "summarize_local_project" in server.tools
    assert server.tools["planned_tool_trajectory"]["func"]("review evidence")["user_goal"] == "review evidence"
    policy_result = server.tools["check_local_policy"]["func"](
        "send_email",
        {"recipient": "maryam@example.com"},
    )
    assert policy_result["passed"] is False


def test_create_mcp_server_imports_real_sdk():
    server = create_mcp_server()

    assert server is not None
