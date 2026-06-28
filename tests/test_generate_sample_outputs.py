import json

from scripts.generate_sample_outputs import generate_sample_outputs


def test_generate_sample_outputs_writes_excerpts(tmp_path):
    brief_path = tmp_path / "brief.md"
    evaluation_path = tmp_path / "evaluation.json"
    golden_path = tmp_path / "golden.json"
    discovery_path = tmp_path / "discovery.json"
    output_dir = tmp_path / "samples"

    brief_path.write_text("# Brief\nUseful output.\n", encoding="utf-8")
    evaluation_path.write_text(
        json.dumps(
            {
                "overall_score": 0.9,
                "grounding_score": 0.8,
                "safety_score": 1.0,
                "testability_score": 0.9,
                "traceability_score": 1.0,
                "total_gaps": 2,
                "total_hypotheses": 2,
                "total_experiment_plans": 2,
                "warnings": [{"message": "review"}],
                "failed_checks": [],
                "metric_details": {
                    "statement_count": 10,
                    "paper_count": 5,
                    "unique_evidence_statement_count": 2,
                    "plan_specificity_score": 0.6,
                },
            }
        ),
        encoding="utf-8",
    )
    golden_path.write_text(
        json.dumps(
            {
                "total_cases": 1,
                "passed_cases": 1,
                "failed_cases": 0,
                "pass_rate": 1.0,
                "results": [{"id": "case_001", "category": "safety", "passed": True}],
            }
        ),
        encoding="utf-8",
    )
    discovery_path.write_text(
        json.dumps(
            {
                "counts": {"gaps": 1, "hypotheses": 1},
                "gaps": [{"gap_id": "gap_001", "gap_text": "A gap.", "source_statement_ids": ["stmt_001"]}],
                "hypotheses": [
                    {
                        "hypothesis_id": "hyp_001",
                        "gap_id": "gap_001",
                        "hypothesis_text": "A testable hypothesis.",
                        "safety_label": "speculative_research_hypothesis",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = generate_sample_outputs(
        output_dir=str(output_dir),
        brief_path=str(brief_path),
        evaluation_path=str(evaluation_path),
        golden_path=str(golden_path),
        discovery_path=str(discovery_path),
    )

    assert set(result["files"]) == {
        "researchnavigator_brief_excerpt.md",
        "evaluation_report_excerpt.json",
        "golden_eval_report_excerpt.json",
        "top_discoveries_excerpt.json",
    }
    assert (output_dir / "researchnavigator_brief_excerpt.md").exists()
    evaluation = json.loads((output_dir / "evaluation_report_excerpt.json").read_text(encoding="utf-8"))
    assert evaluation["overall_score"] == 0.9
