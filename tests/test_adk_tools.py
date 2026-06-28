from app import adk_tools
from app.agent import AGENT_INSTRUCTION, root_agent


def test_agent_module_is_import_safe():
    assert "local-first" in AGENT_INSTRUCTION
    assert "planned_tool_trajectory" in AGENT_INSTRUCTION
    assert "human review" in AGENT_INSTRUCTION
    assert root_agent is None or getattr(root_agent, "name", "") == "research_navigator_agent"


def test_check_local_policy_blocks_external_action():
    result = adk_tools.check_local_policy("send_email", {"recipient": "maryam@example.com"})

    assert result["passed"] is False
    assert "blocked_by_environment" in result["failed_checks"]
    assert result["sanitized_args"]["recipient"] == "[[EMAIL_ADDRESS]]"


def test_generate_local_research_brief_writes_file(monkeypatch, tmp_path):
    monkeypatch.setattr(
        adk_tools,
        "load_processed_data",
        lambda *args, **kwargs: {"statements": [], "gaps": [], "hypotheses": [], "graph": None},
    )
    monkeypatch.setattr(adk_tools, "create_research_brief", lambda data: "# Local Brief\n")

    result = adk_tools.generate_local_research_brief(str(tmp_path / "brief.md"))

    assert result["characters"] == len("# Local Brief\n")
    assert (tmp_path / "brief.md").read_text(encoding="utf-8") == "# Local Brief\n"


def test_run_local_demo_pipeline_delegates(monkeypatch):
    monkeypatch.setattr(adk_tools, "run_demo", lambda reset=False: {"reset": reset, "papers": 1})

    assert adk_tools.run_local_demo_pipeline(reset=True) == {"reset": True, "papers": 1}


def test_search_local_corpus_returns_limited_results(monkeypatch):
    monkeypatch.setattr(
        adk_tools,
        "load_processed_data",
        lambda *args, **kwargs: {"papers": [], "statements": [], "gaps": [], "hypotheses": [], "experiment_plans": []},
    )
    monkeypatch.setattr(
        adk_tools,
        "search_all",
        lambda query, data, filters: {"statements": [{"id": index} for index in range(12)]},
    )

    results = adk_tools.search_local_corpus("test")

    assert len(results["statements"]) == 10


def test_describe_agent_capabilities_exposes_adk_tool_story():
    story = adk_tools.describe_agent_capabilities()
    tool_names = {tool["tool_name"] for tool in story["tools"]}

    assert story["agent_framework"] == "Google ADK"
    assert story["tool_count"] >= 12
    assert "check_local_policy" in tool_names
    assert "describe_agent_capabilities" in tool_names
    assert "planned_tool_trajectory" in tool_names
    assert all("course_concept" in tool for tool in story["tools"])
    assert any(proof["concept"] == "MCP Server" for proof in story["capstone_concept_proofs"])
    assert any(
        item["principle"] == "Policy before side effects"
        for item in story["orchestration_rationale"]
    )
    assert "using generated hypotheses outside the prototype" in story["human_review_gates"]
    assert "Paper text is treated as untrusted data, not instructions." in story["safety_boundaries"]


def test_planned_tool_trajectory_is_ordered_and_policy_gated():
    trajectory = adk_tools.planned_tool_trajectory("review evidence")
    steps = trajectory["steps"]

    assert trajectory["trajectory_type"] == "deterministic_adk_tool_plan"
    assert "opaque summary" in trajectory["why_this_is_agentic"]
    assert [step["order"] for step in steps] == list(range(1, len(steps) + 1))
    assert steps[-1]["tool_name"] == "check_local_policy"
    assert all("policy_boundary" in step for step in steps)
    assert "external_actions_policy_checked" in trajectory["policy_gates"]
    assert "cite local artifact paths or statement IDs" in trajectory["final_answer_contract"]
    assert "state when human review is required" in trajectory["final_answer_contract"]
