import json

from scripts.export_agent_trace import (
    build_agent_trace,
    export_agent_trace,
    validate_agent_trace,
)


def test_agent_trace_has_required_steps_and_safety_order():
    trace = build_agent_trace()

    assert validate_agent_trace(trace) == []
    assert len(trace["steps"]) >= 5
    for step in trace["steps"]:
        assert step["tool_name"]
        assert step["purpose"]
        assert step["input_summary"]
        assert step["output_summary"]

    safety_index = next(
        index for index, step in enumerate(trace["steps"]) if step["step_type"] == "safety_check"
    )
    final_index = next(
        index for index, step in enumerate(trace["steps"]) if step["step_type"] == "final_answer"
    )
    assert safety_index < final_index


def test_agent_trace_final_answer_references_evidence_ids():
    trace = build_agent_trace()
    answer_text = trace["final_answer"]["text"]

    assert trace["final_answer"]["evidence_ids"]
    for evidence_id in trace["final_answer"]["evidence_ids"]:
        assert evidence_id in answer_text


def test_export_agent_trace_writes_deterministic_json(tmp_path):
    output_path = tmp_path / "agent_trace_demo.json"

    trace = export_agent_trace(output_path)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == trace
    assert saved["trace_id"] == "researchnavigator_deterministic_capstone_trace_v1"
