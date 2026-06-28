import io
import json

from tools.logging_tools import log_error, log_info, structured_log


def test_structured_log_text_output():
    stream = io.StringIO()

    record = structured_log(
        "demo.completed",
        message="Done",
        fields={"papers": 5, "score": 0.917},
        stream=stream,
    )

    output = stream.getvalue()
    assert "[INFO] demo.completed - Done" in output
    assert "papers=5" in output
    assert "score=0.917" in output
    assert record["event"] == "demo.completed"


def test_structured_log_json_output():
    stream = io.StringIO()

    structured_log("eval.completed", fields={"passed": True}, stream=stream, json_format=True)

    payload = json.loads(stream.getvalue())
    assert payload["event"] == "eval.completed"
    assert payload["fields"] == {"passed": True}


def test_log_helpers_use_expected_levels():
    info_stream = io.StringIO()
    error_stream = io.StringIO()

    info = structured_log("info.event", stream=info_stream)
    error = structured_log("error.event", level="error", stream=error_stream)

    assert info["level"] == "info"
    assert error["level"] == "error"


def test_invalid_log_level_rejected():
    try:
        structured_log("bad.event", level="fatal")
    except ValueError as exc:
        assert "level must be one of" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_convenience_helpers_emit_records(monkeypatch):
    stream = io.StringIO()
    monkeypatch.setattr("sys.stdout", stream)

    info_record = log_info("pipeline.started", papers=5)

    assert info_record["fields"] == {"papers": 5}
    assert "pipeline.started" in stream.getvalue()

    error_stream = io.StringIO()
    monkeypatch.setattr("sys.stderr", error_stream)
    error_record = log_error("pipeline.failed", message="No papers")

    assert error_record["level"] == "error"
    assert "No papers" in error_stream.getvalue()
