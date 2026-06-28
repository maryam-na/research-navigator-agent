import json

import pytest

from scripts.coverage_report import build_markdown_summary, summarize_coverage_json, write_coverage_summary


def write_coverage_json(path):
    path.write_text(
        json.dumps(
            {
                "totals": {
                    "covered_lines": 80,
                    "num_statements": 100,
                    "missing_lines": 20,
                    "excluded_lines": 3,
                    "percent_covered": 80.0,
                },
                "files": {
                    "tools/a.py": {
                        "summary": {
                            "covered_lines": 45,
                            "num_statements": 50,
                            "missing_lines": 5,
                            "excluded_lines": 0,
                            "percent_covered": 90.0,
                        }
                    },
                    "scripts/b.py": {
                        "summary": {
                            "covered_lines": 35,
                            "num_statements": 50,
                            "missing_lines": 15,
                            "excluded_lines": 3,
                            "percent_covered": 70.0,
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def test_summarize_coverage_json_orders_lowest_files(tmp_path):
    coverage_path = tmp_path / "coverage.json"
    write_coverage_json(coverage_path)

    summary = summarize_coverage_json(str(coverage_path), lowest_file_count=1)

    assert summary["total_percent_covered"] == 80.0
    assert summary["file_count"] == 2
    assert summary["lowest_coverage_files"][0]["file"] == "scripts/b.py"


def test_summarize_coverage_json_rejects_non_positive_lowest_count(tmp_path):
    coverage_path = tmp_path / "coverage.json"
    write_coverage_json(coverage_path)

    with pytest.raises(ValueError):
        summarize_coverage_json(str(coverage_path), lowest_file_count=0)


def test_build_markdown_summary_marks_threshold_status():
    markdown = build_markdown_summary(
        {
            "total_percent_covered": 80.0,
            "covered_lines": 80,
            "missing_lines": 20,
            "num_statements": 100,
            "file_count": 2,
            "lowest_coverage_files": [
                {
                    "file": "scripts/b.py",
                    "percent_covered": 70.0,
                    "num_statements": 50,
                    "missing_lines": 15,
                }
            ],
        },
        min_total=85.0,
    )

    assert "Status: `below threshold`" in markdown
    assert "| `scripts/b.py` | 70.00% | 50 | 15 |" in markdown


def test_write_coverage_summary_writes_markdown(tmp_path):
    coverage_path = tmp_path / "coverage.json"
    markdown_path = tmp_path / "coverage.md"
    write_coverage_json(coverage_path)

    report = write_coverage_summary(str(coverage_path), str(markdown_path), min_total=75.0)

    assert report["ready"] is True
    assert markdown_path.exists()
    assert "Coverage Summary" in markdown_path.read_text(encoding="utf-8")
