import json
from pathlib import Path

import pytest

from ssh_report_summary_worker.agy_cli import AgyClient, AgyError, build_prompt
from ssh_report_summary_worker.models import Report


def report():
    return Report(1, "key-1", "Title", "Firm", None, "https://example.test/a.pdf")


def valid_output():
    return {
        "report_id": 1, "report_unique_key": "key-1", "summary": "summary",
        "key_points": ["point"], "risks": [], "model": "agy",
        "source_pages": [1], "confidence": 0.8,
    }


def test_command_uses_installed_print_interface(tmp_path, monkeypatch):
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps({"type": "object", "required": ["report_id", "report_unique_key", "summary", "key_points", "risks", "model", "source_pages", "confidence"], "properties": {"report_id": {"type": "integer"}, "report_unique_key": {"type": "string"}, "summary": {"type": "string"}, "key_points": {"type": "array"}, "risks": {"type": "array"}, "model": {"type": "string"}, "source_pages": {"type": "array"}, "confidence": {"type": "number"}}, "additionalProperties": False}))
    seen = {}

    def fake_run(command, **kwargs):
        seen.update(command=command, kwargs=kwargs)
        return type("Completed", (), {"returncode": 0, "stdout": json.dumps(valid_output()), "stderr": ""})()

    monkeypatch.setattr("ssh_report_summary_worker.agy_cli.subprocess.run", fake_run)
    result = AgyClient("agy", schema).summarize(report(), tmp_path / "x.pdf")
    assert result.summary == "summary"
    assert seen["command"][:3] == ["agy", "--print", seen["command"][2]]
    assert "--output-format" in seen["command"]
    assert seen["kwargs"]["shell"] is False


def test_identifier_mismatch_is_rejected(tmp_path, monkeypatch):
    schema = tmp_path / "schema.json"
    schema.write_text(Path("schemas/summary_output.schema.json").read_text())
    output = valid_output()
    output["report_id"] = 99
    monkeypatch.setattr("ssh_report_summary_worker.agy_cli.subprocess.run", lambda *a, **k: type("C", (), {"returncode": 0, "stdout": json.dumps(output), "stderr": ""})())
    with pytest.raises(AgyError, match="identifiers"):
        AgyClient("agy", schema).summarize(report(), tmp_path / "x.pdf")


def test_accepts_agy_metadata_wrapper(tmp_path, monkeypatch):
    schema = tmp_path / "schema.json"
    schema.write_text(Path("schemas/summary_output.schema.json").read_text())
    wrapped = {"status": "success", "structured_output": valid_output(), "conversation_id": "x"}
    monkeypatch.setattr("ssh_report_summary_worker.agy_cli.subprocess.run", lambda *a, **k: type("C", (), {"returncode": 0, "stdout": json.dumps(wrapped), "stderr": ""})())
    assert AgyClient("agy", schema).summarize(report(), tmp_path / "x.pdf").summary == "summary"
