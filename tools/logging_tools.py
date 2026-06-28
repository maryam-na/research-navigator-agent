"""Small structured logging helpers for local scripts."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any, TextIO


VALID_LEVELS = {"debug", "info", "warning", "error"}


def structured_log(
    event: str,
    level: str = "info",
    message: str | None = None,
    fields: dict[str, Any] | None = None,
    stream: TextIO | None = None,
    json_format: bool = False,
) -> dict[str, Any]:
    """Emit and return a deterministic structured log record."""

    if not event or not event.strip():
        raise ValueError("event must be a non-empty string.")
    normalized_level = level.lower().strip()
    if normalized_level not in VALID_LEVELS:
        raise ValueError(f"level must be one of: {', '.join(sorted(VALID_LEVELS))}")

    record: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "level": normalized_level,
        "event": event.strip(),
        "message": message or "",
        "fields": fields or {},
    }
    output_stream = stream or (sys.stderr if normalized_level == "error" else sys.stdout)
    if json_format:
        print(json.dumps(record, sort_keys=True), file=output_stream)
    else:
        field_text = _format_fields(record["fields"])
        suffix = f" {field_text}" if field_text else ""
        text = f"[{normalized_level.upper()}] {record['event']}"
        if record["message"]:
            text += f" - {record['message']}"
        print(f"{text}{suffix}", file=output_stream)
    return record


def log_info(event: str, message: str | None = None, **fields: Any) -> dict[str, Any]:
    """Emit an info log."""

    return structured_log(event, level="info", message=message, fields=fields)


def log_warning(event: str, message: str | None = None, **fields: Any) -> dict[str, Any]:
    """Emit a warning log."""

    return structured_log(event, level="warning", message=message, fields=fields)


def log_error(event: str, message: str | None = None, **fields: Any) -> dict[str, Any]:
    """Emit an error log."""

    return structured_log(event, level="error", message=message, fields=fields)


def _format_fields(fields: dict[str, Any]) -> str:
    if not fields:
        return ""
    return " ".join(f"{key}={_format_value(value)}" for key, value in sorted(fields.items()))


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True)
    return str(value)
