from pathlib import Path

from scripts.dependency_audit import audit_dependencies


def write_project(root: Path, dependencies: list[str], lock_names: list[str]) -> None:
    root.joinpath("pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "fixture"',
                'version = "0.1.0"',
                "dependencies = [",
                *[f'  "{dependency}",' for dependency in dependencies],
                "]",
                "",
                "[project.optional-dependencies]",
                'dev = ["pytest>=8.2.0"]',
            ]
        ),
        encoding="utf-8",
    )
    lock_text = ["version = 1", "requires-python = \">=3.11\"", ""]
    for index, name in enumerate(lock_names):
        lock_text.extend(
            [
                "[[package]]",
                f'name = "{name}"',
                f'version = "1.0.{index}"',
                "",
            ]
        )
    root.joinpath("uv.lock").write_text("\n".join(lock_text), encoding="utf-8")


def test_dependency_audit_flags_missing_core_dependency(tmp_path):
    write_project(tmp_path, ["pydantic>=2.8.0"], ["pydantic", "pytest"])

    report = audit_dependencies(str(tmp_path), strict_unused=False)

    assert report["ready"] is False
    assert any(
        check["category"] == "runtime_dependency"
        and check["status"] == "fail"
        for check in report["checks"]
    )


def test_dependency_audit_warns_on_unused_direct_dependency(tmp_path):
    write_project(
        tmp_path,
        [
            "google-adk>=1.0.0",
            "streamlit>=1.36.0",
            "pydantic>=2.8.0",
            "networkx>=3.3",
            "pypdf>=4.2.0",
            "pandas>=2.2.0",
            "duckdb>=1.0.0",
        ],
        ["google-adk", "streamlit", "pydantic", "networkx", "pypdf", "pandas", "duckdb", "pytest"],
    )
    source_path = tmp_path / "app" / "main.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "import google.adk\nimport streamlit\nimport pydantic\nimport networkx\nimport pypdf\nimport pandas\n",
        encoding="utf-8",
    )

    report = audit_dependencies(str(tmp_path), strict_unused=False)

    assert report["ready"] is True
    assert any(
        check["category"] == "direct_usage"
        and check["name"] == "duckdb"
        and check["status"] == "warn"
        for check in report["checks"]
    )


def test_dependency_audit_strict_unused_fails_unused_direct_dependency(tmp_path):
    write_project(
        tmp_path,
        [
            "google-adk>=1.0.0",
            "streamlit>=1.36.0",
            "pydantic>=2.8.0",
            "networkx>=3.3",
            "pypdf>=4.2.0",
            "pandas>=2.2.0",
            "duckdb>=1.0.0",
        ],
        ["google-adk", "streamlit", "pydantic", "networkx", "pypdf", "pandas", "duckdb", "pytest"],
    )

    report = audit_dependencies(str(tmp_path), strict_unused=True)

    assert report["ready"] is False
    assert any(
        check["category"] == "direct_usage"
        and check["name"] == "duckdb"
        and check["status"] == "fail"
        for check in report["checks"]
    )


def test_dependency_audit_fails_when_declared_dependency_missing_from_lock(tmp_path):
    write_project(
        tmp_path,
        [
            "google-adk>=1.0.0",
            "streamlit>=1.36.0",
            "pydantic>=2.8.0",
            "networkx>=3.3",
            "pypdf>=4.2.0",
            "pandas>=2.2.0",
        ],
        ["google-adk", "streamlit", "pydantic", "networkx", "pypdf", "pytest"],
    )

    report = audit_dependencies(str(tmp_path), strict_unused=False)

    assert report["ready"] is False
    assert any(
        check["category"] == "lock_coverage"
        and check["name"] == "pandas"
        and check["status"] == "fail"
        for check in report["checks"]
    )
