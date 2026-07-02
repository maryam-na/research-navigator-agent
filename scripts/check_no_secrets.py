"""Scan project text files for real-looking secrets before submission."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


TEXT_SUFFIXES = {
    ".cfg",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "htmlcov",
    "venv",
}
EXCLUDED_PREFIXES = {
    ("data", "papers"),
    ("data", "processed"),
}
PLACEHOLDER_MARKERS = (
    "abc123",
    "abcdef",
    "dummy",
    "example",
    "fake",
    "placeholder",
    "redacted",
    "sample",
    "test",
    "xxxx",
)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    (
        "secret_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|secret|password|passwd)\b"
            r"\s*[:=]\s*['\"]?([A-Za-z0-9_./+=-]{16,})"
        ),
    ),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)


@dataclass(frozen=True)
class SecretFinding:
    path: str
    line: int
    kind: str
    preview: str


def scan_for_secrets(project_root: str | Path = ".") -> dict:
    """Return a deterministic no-secrets scan report."""

    root = Path(project_root)
    findings: list[SecretFinding] = []
    scanned_files = 0
    for path in _iter_text_files(root):
        scanned_files += 1
        findings.extend(_scan_file(root, path))
    return {
        "ready": not findings,
        "summary": {
            "scanned_files": scanned_files,
            "findings": len(findings),
        },
        "findings": [asdict(finding) for finding in findings],
    }


def _iter_text_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in TEXT_SUFFIXES else []
    paths = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if _is_excluded(root, path):
            continue
        paths.append(path)
    return sorted(paths)


def _is_excluded(root: Path, path: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    if any(part in EXCLUDED_DIRS for part in parts):
        return True
    return any(parts[: len(prefix)] == prefix for prefix in EXCLUDED_PREFIXES)


def _scan_file(root: Path, path: Path) -> list[SecretFinding]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    findings: list[SecretFinding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(line):
                matched_text = match.group(0)
                value = match.group(1) if match.groups() else matched_text
                if _is_placeholder(value):
                    continue
                findings.append(
                    SecretFinding(
                        path=str(path.relative_to(root) if path.is_relative_to(root) else path),
                        line=line_number,
                        kind=kind,
                        preview=_redacted_preview(matched_text),
                    )
                )
    return findings


def _is_placeholder(value: str) -> bool:
    normalized = value.lower()
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def _redacted_preview(value: str) -> str:
    stripped = value.strip()
    if len(stripped) <= 8:
        return "[[REDACTED]]"
    return f"{stripped[:4]}...{stripped[-4:]}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan text files for real-looking secrets.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--json", action="store_true", help="Print the full scan report as JSON.")
    parser.add_argument(
        "--output-path",
        default="data/generated/no_secrets_report.json",
        help="Where to write the JSON scan report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = scan_for_secrets(args.project_root)
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print(
            "No-secrets scan: "
            f"ready={report['ready']} scanned={summary['scanned_files']} "
            f"findings={summary['findings']} report={args.output_path}"
        )
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
