from tools.policy_tools import (
    detect_sensitive_context,
    is_tool_allowed,
    load_policy_config,
    sanitize_action_args,
    sanitize_context_text,
    validate_tool_action,
)


def test_load_policy_config_reads_project_yaml():
    policies = load_policy_config("specs/policies.yaml")

    assert policies["default_environment"] == "localhost"
    assert "send_email" in policies["environments"]["localhost"]["blocked_tools"]
    assert "extract_pdf_text" in policies["roles"]["researcher"]["allowed_tools"]


def test_tool_policy_blocks_environment_actions():
    result = is_tool_allowed("send_email", role="maintainer", environment="localhost")

    assert result["passed"] is False
    assert result["reason"] == "blocked_by_environment"


def test_tool_policy_enforces_role_allowlist():
    denied = is_tool_allowed("extract_pdf_text", role="viewer", environment="localhost")
    allowed = is_tool_allowed("search_statements", role="viewer", environment="localhost")

    assert denied["passed"] is False
    assert denied["reason"] == "not_allowed_for_role"
    assert allowed["passed"] is True


def test_sensitive_context_detection_and_sanitization():
    text = "Contact maryam@example.com with api_key=abcdef1234567890 and http://127.0.0.1:8501."

    detected = detect_sensitive_context(text)
    sanitized = sanitize_context_text(text)

    assert detected["passed"] is False
    assert "email_address" in detected["matched_patterns"]
    assert "[[EMAIL_ADDRESS]]" in sanitized
    assert "[[SECRET_VALUE]]" in sanitized
    assert "[[PRIVATE_URL]]" in sanitized


def test_validate_tool_action_returns_sanitized_args():
    result = validate_tool_action(
        "search_statements",
        {"query": "email maryam@example.com", "nested": {"path": "/Users/maryam/private.txt"}},
        role="viewer",
        environment="localhost",
    )

    assert result["passed"] is False
    assert "sensitive_context_detected" in result["failed_checks"]
    assert result["sanitized_args"]["query"] == "email [[EMAIL_ADDRESS]]"
    assert result["sanitized_args"]["nested"]["path"] == "[[LOCAL_PATH]]"


def test_sanitize_action_args_handles_lists():
    sanitized = sanitize_action_args({"items": ["maryam@example.com", "safe"]})

    assert sanitized == {"items": ["[[EMAIL_ADDRESS]]", "safe"]}
