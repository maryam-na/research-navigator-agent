"""Deterministic local policy checks for ResearchNavigator tool actions."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


DEFAULT_POLICY_PATH = Path("specs/policies.yaml")

DEFAULT_POLICIES: dict[str, Any] = {
    "default_environment": "localhost",
    "default_role": "researcher",
    "environments": {
        "localhost": {
            "blocked_tools": [
                "send_email",
                "deploy_cloud",
                "external_web_search",
                "train_model",
                "fine_tune_model",
                "write_outside_workspace",
            ]
        }
    },
    "roles": {
        "viewer": {
            "allowed_tools": [
                "load_processed_data",
                "search_statements",
                "search_gaps",
                "search_hypotheses",
                "view_dashboard",
            ]
        },
        "researcher": {
            "allowed_tools": [
                "extract_pdf_text",
                "chunk_text",
                "initialize_database",
                "save_paper",
                "save_chunk",
                "save_statement",
                "get_papers",
                "get_chunks",
                "get_statements",
                "extract_research_statements",
                "filter_statements",
                "build_research_graph",
                "discover_research_gaps",
                "generate_hypotheses",
                "generate_experiment_plan",
                "evaluate_outputs",
                "load_processed_data",
                "search_statements",
                "search_gaps",
                "search_hypotheses",
                "view_dashboard",
            ]
        },
        "maintainer": {"allowed_tools": ["*"]},
    },
    "sensitive_patterns": [
        "email_address",
        "api_key",
        "private_url",
        "absolute_home_path",
    ],
}

SENSITIVE_PATTERN_REGEX = {
    "email_address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "api_key": re.compile(r"\b(?:api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}", re.I),
    "private_url": re.compile(r"https?://(?:localhost|127\.0\.0\.1|10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[0-1])\.)[^\s]+", re.I),
    "absolute_home_path": re.compile(r"/Users/[A-Za-z0-9._-]+/[^\s]+"),
}

SENSITIVE_REPLACEMENTS = {
    "email_address": "[[EMAIL_ADDRESS]]",
    "api_key": "[[SECRET_VALUE]]",
    "private_url": "[[PRIVATE_URL]]",
    "absolute_home_path": "[[LOCAL_PATH]]",
}


def load_policy_config(path: str | Path = DEFAULT_POLICY_PATH) -> dict[str, Any]:
    """Load local policy YAML, falling back to built-in defaults if it is absent."""

    policy_path = Path(path)
    if not policy_path.exists():
        return DEFAULT_POLICIES.copy()
    parsed = _parse_simple_yaml(policy_path.read_text(encoding="utf-8"))
    return _merge_policy_defaults(parsed)


def is_tool_allowed(
    tool_name: str,
    role: str = "researcher",
    environment: str = "localhost",
    policies: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check deterministic role and environment permissions for a tool name."""

    if not tool_name or not tool_name.strip():
        raise ValueError("tool_name must be a non-empty string.")
    active_policies = policies or load_policy_config()
    blocked_tools = _blocked_tools(active_policies, environment)
    allowed_tools = _allowed_tools(active_policies, role)
    normalized_tool = tool_name.strip()

    if normalized_tool in blocked_tools:
        return {
            "passed": False,
            "tool_name": normalized_tool,
            "reason": "blocked_by_environment",
            "role": role,
            "environment": environment,
        }
    if "*" in allowed_tools or normalized_tool in allowed_tools:
        return {
            "passed": True,
            "tool_name": normalized_tool,
            "reason": "allowed",
            "role": role,
            "environment": environment,
        }
    return {
        "passed": False,
        "tool_name": normalized_tool,
        "reason": "not_allowed_for_role",
        "role": role,
        "environment": environment,
    }


def detect_sensitive_context(text: str, policies: dict[str, Any] | None = None) -> dict[str, Any]:
    """Detect sensitive local context that should not be passed into agent actions."""

    active_policies = policies or load_policy_config()
    enabled_patterns = active_policies.get("sensitive_patterns", DEFAULT_POLICIES["sensitive_patterns"])
    matches = {}
    for pattern_name in enabled_patterns:
        regex = SENSITIVE_PATTERN_REGEX.get(str(pattern_name))
        if not regex:
            continue
        found = sorted(set(regex.findall(text or "")))
        if found:
            matches[str(pattern_name)] = found
    return {
        "passed": not matches,
        "sensitive_context_detected": bool(matches),
        "matched_patterns": matches,
    }


def sanitize_context_text(text: str, policies: dict[str, Any] | None = None) -> str:
    """Replace sensitive values with stable placeholders."""

    active_policies = policies or load_policy_config()
    sanitized = text or ""
    for pattern_name in active_policies.get("sensitive_patterns", DEFAULT_POLICIES["sensitive_patterns"]):
        regex = SENSITIVE_PATTERN_REGEX.get(str(pattern_name))
        replacement = SENSITIVE_REPLACEMENTS.get(str(pattern_name), "[[REDACTED]]")
        if regex:
            sanitized = regex.sub(replacement, sanitized)
    return sanitized


def validate_tool_action(
    tool_name: str,
    action_args: dict[str, Any] | None = None,
    role: str = "researcher",
    environment: str = "localhost",
    policies: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a proposed tool action before execution."""

    active_policies = policies or load_policy_config()
    permission = is_tool_allowed(tool_name, role=role, environment=environment, policies=active_policies)
    action_text = _stringify_action_args(action_args or {})
    sensitive_context = detect_sensitive_context(action_text, policies=active_policies)
    sanitized_args = sanitize_action_args(action_args or {}, policies=active_policies)
    passed = permission["passed"] and sensitive_context["passed"]
    failed_checks = []
    if not permission["passed"]:
        failed_checks.append(permission["reason"])
    if not sensitive_context["passed"]:
        failed_checks.append("sensitive_context_detected")
    return {
        "passed": passed,
        "tool_name": tool_name,
        "permission": permission,
        "sensitive_context": sensitive_context,
        "sanitized_args": sanitized_args,
        "failed_checks": failed_checks,
    }


def sanitize_action_args(action_args: dict[str, Any], policies: dict[str, Any] | None = None) -> dict[str, Any]:
    """Recursively sanitize string values in tool arguments."""

    active_policies = policies or load_policy_config()
    sanitized = {}
    for key, value in action_args.items():
        sanitized[key] = _sanitize_value(value, active_policies)
    return sanitized


def _sanitize_value(value: Any, policies: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return sanitize_context_text(value, policies=policies)
    if isinstance(value, list):
        return [_sanitize_value(item, policies) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_value(item, policies) for key, item in value.items()}
    return value


def _stringify_action_args(action_args: dict[str, Any]) -> str:
    values = []
    for value in action_args.values():
        if isinstance(value, dict):
            values.append(_stringify_action_args(value))
        elif isinstance(value, list):
            values.extend(str(item) for item in value)
        else:
            values.append(str(value))
    return " ".join(values)


def _blocked_tools(policies: dict[str, Any], environment: str) -> set[str]:
    environment_config = policies.get("environments", {}).get(environment, {})
    return {str(item) for item in environment_config.get("blocked_tools", [])}


def _allowed_tools(policies: dict[str, Any], role: str) -> set[str]:
    role_config = policies.get("roles", {}).get(role, {})
    return {str(item) for item in role_config.get("allowed_tools", [])}


def _merge_policy_defaults(parsed: dict[str, Any]) -> dict[str, Any]:
    merged = DEFAULT_POLICIES.copy()
    merged.update(parsed)
    merged["environments"] = {**DEFAULT_POLICIES["environments"], **parsed.get("environments", {})}
    merged["roles"] = {**DEFAULT_POLICIES["roles"], **parsed.get("roles", {})}
    return merged


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the restricted YAML shape used by specs/policies.yaml."""

    lines = []
    for raw_line in text.splitlines():
        stripped = raw_line.split("#", 1)[0].rstrip()
        if not stripped.strip():
            continue
        lines.append((len(stripped) - len(stripped.lstrip(" ")), stripped.strip()))

    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    for index, (indent, content) in enumerate(lines):
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if content.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError("Invalid policy YAML: list item without list parent.")
            parent.append(_parse_scalar(content[2:]))
            continue
        key, value = _split_key_value(content)
        if not isinstance(parent, dict):
            raise ValueError("Invalid policy YAML: mapping entry without dict parent.")
        if value == "":
            child = [] if _next_child_is_list(lines, index, indent) else {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(value)
    return root


def _split_key_value(content: str) -> tuple[str, str]:
    if ":" not in content:
        raise ValueError(f"Invalid policy YAML line: {content}")
    key, value = content.split(":", 1)
    return key.strip(), value.strip()


def _next_child_is_list(lines: list[tuple[int, str]], index: int, indent: int) -> bool:
    for next_indent, next_content in lines[index + 1 :]:
        if next_indent <= indent:
            return False
        return next_content.startswith("- ")
    return False


def _parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    return value
