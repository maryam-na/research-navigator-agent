"""Audit local Python dependencies without network calls."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.logging_tools import log_error, log_info


DEPENDENCY_IMPORT_MAP = {
    "google-adk": ("google",),
    "streamlit": ("streamlit",),
    "pydantic": ("pydantic",),
    "duckdb": ("duckdb",),
    "networkx": ("networkx",),
    "pypdf": ("pypdf",),
    "python-dotenv": ("dotenv",),
    "pandas": ("pandas",),
    "typer": ("typer",),
    "rich": ("rich",),
    "pytest": ("pytest",),
    "pytest-cov": ("pytest_cov",),
    "ruff": ("ruff",),
    "mypy": ("mypy",),
    "jsonschema": ("jsonschema",),
}

EXPECTED_RUNTIME_DEPENDENCIES = {
    "google-adk",
    "streamlit",
    "pydantic",
    "networkx",
    "pypdf",
    "pandas",
}

LOCAL_FIRST_RISKY_DIRECT_DEPENDENCIES = {
    "boto3",
    "google-cloud-aiplatform",
    "openai",
    "anthropic",
    "wandb",
    "mlflow",
}

SOURCE_DIRS = ("app", "tools", "scripts", "ui", "tests")


def _resolve_local_path(path_value: str, label: str) -> Path:
    if not path_value or not path_value.strip():
        raise ValueError(f"{label} must be a non-empty local path.")
    parsed = urlparse(path_value)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError(f"{label} must be a local path.")
    return Path(parsed.path if parsed.scheme == "file" else path_value).expanduser()


def audit_dependencies(project_root: str = ".", strict_unused: bool = False) -> dict[str, Any]:
    """Return an offline dependency audit report."""

    root = _resolve_local_path(project_root, "project_root")
    checks: list[dict[str, str]] = []
    if not root.exists() or not root.is_dir():
        checks.append(_result("project", "project_root", "fail", f"Project root is missing: {root}"))
        return _build_report(root, [], [], {}, checks)

    pyproject_path = root / "pyproject.toml"
    lock_path = root / "uv.lock"
    if not pyproject_path.exists():
        checks.append(_result("dependency_file", "pyproject.toml", "fail", "pyproject.toml is missing."))
        return _build_report(root, [], [], {}, checks)

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    runtime_specs = _dependency_specs(pyproject.get("project", {}).get("dependencies", []))
    optional_specs = _optional_dependency_specs(
        pyproject.get("project", {}).get("optional-dependencies", {})
    )
    all_specs = {**runtime_specs}
    for group_specs in optional_specs.values():
        all_specs.update(group_specs)

    locked_versions: dict[str, str] = {}
    if not lock_path.exists():
        checks.append(_result("dependency_file", "uv.lock", "fail", "uv.lock is missing."))
    else:
        locked_versions = _locked_versions(lock_path)
        checks.append(_result("dependency_file", "uv.lock", "pass", "uv.lock exists and is parseable."))

    imported_modules = _discover_imported_modules(root, SOURCE_DIRS)
    checks.extend(_check_required_runtime_dependencies(runtime_specs))
    checks.extend(_check_lock_coverage(all_specs, locked_versions))
    checks.extend(_check_specifiers(runtime_specs, optional_specs))
    checks.extend(_check_usage(runtime_specs, optional_specs, imported_modules, strict_unused))
    checks.extend(_check_local_first_risks(runtime_specs))
    checks.extend(_check_dependency_size(runtime_specs, optional_specs, locked_versions))

    return _build_report(root, runtime_specs, optional_specs, locked_versions, checks)


def _dependency_specs(raw_specs: Iterable[str]) -> dict[str, str]:
    specs: dict[str, str] = {}
    for raw_spec in raw_specs:
        name = _dependency_name(raw_spec)
        specs[name] = raw_spec
    return dict(sorted(specs.items()))


def _optional_dependency_specs(raw_groups: dict[str, list[str]]) -> dict[str, dict[str, str]]:
    groups: dict[str, dict[str, str]] = {}
    for group_name, raw_specs in raw_groups.items():
        groups[group_name] = _dependency_specs(raw_specs)
    return dict(sorted(groups.items()))


def _dependency_name(raw_spec: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", raw_spec)
    if not match:
        raise ValueError(f"Could not parse dependency specifier: {raw_spec}")
    return match.group(1).lower().replace("_", "-")


def _locked_versions(lock_path: Path) -> dict[str, str]:
    payload = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    packages = payload.get("package", [])
    versions = {
        str(package.get("name", "")).lower().replace("_", "-"): str(package.get("version", ""))
        for package in packages
        if package.get("name") and package.get("version")
    }
    return dict(sorted(versions.items()))


def _discover_imported_modules(root: Path, source_dirs: Iterable[str]) -> set[str]:
    imported: set[str] = set()
    for source_dir in source_dirs:
        base = root / source_dir
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
    return imported


def _check_required_runtime_dependencies(runtime_specs: dict[str, str]) -> list[dict[str, str]]:
    checks = []
    missing = sorted(EXPECTED_RUNTIME_DEPENDENCIES - set(runtime_specs))
    checks.append(
        _result(
            "runtime_dependency",
            "expected_core_stack",
            "pass" if not missing else "fail",
            "Core MVP dependencies are declared."
            if not missing
            else f"Missing expected runtime dependencies: {', '.join(missing)}.",
        )
    )
    return checks


def _check_lock_coverage(
    all_specs: dict[str, str],
    locked_versions: dict[str, str],
) -> list[dict[str, str]]:
    if not locked_versions:
        return []
    checks = []
    for name in sorted(all_specs):
        checks.append(
            _result(
                "lock_coverage",
                name,
                "pass" if name in locked_versions else "fail",
                f"Locked at {locked_versions[name]}." if name in locked_versions else "Declared dependency is missing from uv.lock.",
            )
        )
    return checks


def _check_specifiers(
    runtime_specs: dict[str, str],
    optional_specs: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    checks = []
    grouped_specs = [("runtime", runtime_specs), *sorted(optional_specs.items())]
    for group_name, specs in grouped_specs:
        for name, raw_spec in specs.items():
            has_lower_bound = any(operator in raw_spec for operator in (">=", "==", "~="))
            checks.append(
                _result(
                    "version_specifier",
                    f"{group_name}:{name}",
                    "pass" if has_lower_bound else "warn",
                    "Dependency has a lower bound or exact pin."
                    if has_lower_bound
                    else "Dependency has no lower bound; reproducibility depends on uv.lock.",
                )
            )
    return checks


def _check_usage(
    runtime_specs: dict[str, str],
    optional_specs: dict[str, dict[str, str]],
    imported_modules: set[str],
    strict_unused: bool,
) -> list[dict[str, str]]:
    checks = []
    status_for_unused = "fail" if strict_unused else "warn"
    for name in sorted(runtime_specs):
        modules = DEPENDENCY_IMPORT_MAP.get(name, (name.replace("-", "_"),))
        used = any(module in imported_modules for module in modules)
        checks.append(
            _result(
                "direct_usage",
                name,
                "pass" if used else status_for_unused,
                f"Detected import module(s): {', '.join(modules)}."
                if used
                else "No direct import detected in app/tools/scripts/ui/tests; keep only if intentionally planned.",
            )
        )

    for group_name, specs in sorted(optional_specs.items()):
        for name in sorted(specs):
            modules = DEPENDENCY_IMPORT_MAP.get(name, (name.replace("-", "_"),))
            used = any(module in imported_modules for module in modules)
            status = "pass" if used or group_name == "dev" else "warn"
            message = (
                f"Detected import module(s): {', '.join(modules)}."
                if used
                else f"Optional dependency belongs to `{group_name}` tooling and is not required at runtime."
            )
            checks.append(_result("optional_usage", f"{group_name}:{name}", status, message))
    return checks


def _check_local_first_risks(runtime_specs: dict[str, str]) -> list[dict[str, str]]:
    risky = sorted(LOCAL_FIRST_RISKY_DIRECT_DEPENDENCIES & set(runtime_specs))
    return [
        _result(
            "local_first_risk",
            "cloud_or_training_sdks",
            "pass" if not risky else "fail",
            "No risky cloud/model-provider SDKs are declared as direct runtime dependencies."
            if not risky
            else f"Risky direct dependencies for local MVP: {', '.join(risky)}.",
        )
    ]


def _check_dependency_size(
    runtime_specs: dict[str, str],
    optional_specs: dict[str, dict[str, str]],
    locked_versions: dict[str, str],
) -> list[dict[str, str]]:
    direct_count = len(runtime_specs)
    optional_count = sum(len(specs) for specs in optional_specs.values())
    locked_count = len(locked_versions)
    return [
        _result(
            "dependency_size",
            "runtime_direct_count",
            "pass" if direct_count <= 12 else "warn",
            f"Runtime direct dependency count: {direct_count}.",
        ),
        _result(
            "dependency_size",
            "optional_direct_count",
            "pass" if optional_count <= 8 else "warn",
            f"Optional direct dependency count: {optional_count}.",
        ),
        _result(
            "dependency_size",
            "locked_package_count",
            "pass" if not locked_versions or locked_count <= 250 else "warn",
            f"Locked package count: {locked_count}.",
        ),
    ]


def _build_report(
    root: Path,
    runtime_specs: dict[str, str] | list[Any],
    optional_specs: dict[str, dict[str, str]] | list[Any],
    locked_versions: dict[str, str],
    checks: list[dict[str, str]],
) -> dict[str, Any]:
    failed = [check for check in checks if check["status"] == "fail"]
    warnings = [check for check in checks if check["status"] == "warn"]
    passed = [check for check in checks if check["status"] == "pass"]
    runtime_names = sorted(runtime_specs) if isinstance(runtime_specs, dict) else []
    optional_groups = {
        group_name: sorted(specs)
        for group_name, specs in optional_specs.items()
    } if isinstance(optional_specs, dict) else {}
    return {
        "ready": not failed,
        "project_root": str(root),
        "summary": {
            "passed": len(passed),
            "warnings": len(warnings),
            "failed": len(failed),
            "total": len(checks),
        },
        "dependencies": {
            "runtime_direct": runtime_names,
            "optional_direct": optional_groups,
            "locked_package_count": len(locked_versions),
        },
        "recommendations": _recommendations(checks),
        "checks": checks,
    }


def _recommendations(checks: list[dict[str, str]]) -> list[str]:
    recommendations = []
    unused = [
        check["name"]
        for check in checks
        if check["category"] == "direct_usage" and check["status"] in {"warn", "fail"}
    ]
    if unused:
        recommendations.append(
            "Review unused direct runtime dependencies before final submission: "
            + ", ".join(sorted(unused))
            + "."
        )
    if any(check["category"] == "lock_coverage" and check["status"] == "fail" for check in checks):
        recommendations.append("Run `uv lock` after dependency changes so declared dependencies are reproducible.")
    if any(check["category"] == "local_first_risk" and check["status"] == "fail" for check in checks):
        recommendations.append("Remove direct cloud or model-provider SDKs unless the local-first scope changes.")
    if not recommendations:
        recommendations.append("Dependency posture is acceptable for the local deterministic MVP.")
    return recommendations


def _result(category: str, name: str, status: str, message: str) -> dict[str, str]:
    return {
        "category": category,
        "name": name,
        "status": status,
        "message": message,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit local dependency posture without network calls.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict-unused", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print the full dependency audit as JSON.")
    parser.add_argument(
        "--output-path",
        default="data/processed/dependency_audit_report.json",
        help="Where to write the JSON dependency audit report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = audit_dependencies(args.project_root, strict_unused=args.strict_unused)
        output_path = _resolve_local_path(args.output_path, "output_path")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        log_error("dependency_audit.failed", str(exc))
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        log_info(
            "dependency_audit.completed",
            ready=report["ready"],
            passed=summary["passed"],
            warnings=summary["warnings"],
            failed=summary["failed"],
            report=args.output_path,
        )
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
