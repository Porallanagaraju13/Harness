"""Tests for secret scrubbing and multi-dataset publish."""

import json

from harnessdiff.agent_loop import Trace
from harnessdiff.publish import discover_datasets, publish_datasets
from harnessdiff.sanitize import scrub_jsonl_line, scrub_value


def test_scrub_api_key_fields():
    payload = {
        "api_key": "sk-secret-value",
        "headers": {"Authorization": "Bearer tok123", "Content-Type": "application/json"},
        "safe": "hello",
        "nested": {"GEMINI_API_KEY": "AIzaSyFakeKey1234567890"},
    }
    scrubbed = scrub_value(payload)
    assert scrubbed["api_key"] == "[REDACTED]"
    assert scrubbed["headers"]["Authorization"] == "[REDACTED]"
    assert scrubbed["safe"] == "hello"
    assert scrubbed["nested"]["GEMINI_API_KEY"] == "[REDACTED]"


def test_scrub_string_patterns():
    text = "Authorization: Bearer abc.def Authorization: Bearer xyz"
    out = scrub_value(text)
    assert "Bearer abc" not in out
    assert "[REDACTED]" in out


def test_trace_save_scrubs_secrets(tmp_path):
    trace = Trace(
        task_id="t1",
        config={"api_key": "sk-should-not-appear", "use_sandbox": True},
        result={"status": "ok", "final_message": "done key=AIzaSyFakeKeyABCDEFG"},
    )
    path = tmp_path / "t_trace.jsonl"
    trace.save(path)
    raw = path.read_text()
    assert "sk-should-not-appear" not in raw
    assert "AIzaSyFakeKeyABCDEFG" not in raw
    assert "[REDACTED]" in raw


def test_discover_and_publish_datasets(tmp_path):
    results_root = tmp_path / "results"
    mock_dir = results_root / "mock"
    gem_dir = results_root / "gemini-3.8-flash"
    mock_dir.mkdir(parents=True)
    gem_dir.mkdir(parents=True)

    mock_payload = {
        "timestamp": "2026-01-01T00:00:00",
        "model": {
            "spec": "mock",
            "provider": "mock",
            "model_id": "mock",
            "display_name": "Mock model",
        },
        "runs": [],
        "summary": {"baseline": {"real_success_rate": 0.5}},
    }
    gem_payload = {
        "timestamp": "2026-01-02T00:00:00",
        "model": {
            "spec": "gemini:gemini-3.8-flash",
            "provider": "gemini",
            "model_id": "gemini-3.8-flash",
            "display_name": "Gemini (gemini-3.8-flash)",
        },
        "runs": [],
        "summary": {
            "baseline": {"real_success_rate": 0.4},
            "layer_verification": {"real_success_rate": 0.7},
        },
        "api_key": "sk-leak",
    }

    (mock_dir / "ablation_results.json").write_text(json.dumps(mock_payload))
    (gem_dir / "ablation_results.json").write_text(json.dumps(gem_payload))
    (mock_dir / "baseline_file_creation_trace.jsonl").write_text(
        json.dumps({"type": "trace_start", "api_key": "sk-trace-leak"}) + "\n"
    )
    (gem_dir / "baseline_file_creation_trace.jsonl").write_text(
        json.dumps({"type": "step", "Authorization": "Bearer leak"}) + "\n"
    )
    (gem_dir / "layer_verification_file_creation_trace.jsonl").write_text(
        json.dumps({"type": "trace_end", "result": {"ok": True}}) + "\n"
    )

    discovered = discover_datasets(results_root)
    assert {d["id"] for d in discovered} == {"mock", "gemini-3.8-flash"}

    web_data = tmp_path / "web" / "public" / "data"
    summary = publish_datasets(results_root=results_root, web_data=web_data)
    ids = [p["id"] for p in summary["published"]]
    assert ids == ["mock", "gemini-3.8-flash"] or set(ids) == {"mock", "gemini-3.8-flash"}

    index = json.loads((web_data / "index.json").read_text())
    assert len(index["datasets"]) == 2
    assert any(not d.get("is_mock") for d in index["datasets"])

    published_gem = json.loads(
        (web_data / "gemini-3.8-flash" / "ablation_results.json").read_text()
    )
    assert (
        published_gem.get("api_key") == "[REDACTED]"
        or "api_key" not in published_gem
        or published_gem["api_key"] == "[REDACTED]"
    )
    # scrub_value redacts the key value
    assert published_gem["api_key"] == "[REDACTED]"

    trace_text = (web_data / "mock" / "baseline_file_creation_trace.jsonl").read_text()
    assert "sk-trace-leak" not in trace_text
    assert "[REDACTED]" in trace_text


def test_scrub_jsonl_line_invalid_json():
    line = "Authorization: Bearer plaintext-token-value"
    out = scrub_jsonl_line(line)
    assert "plaintext-token-value" not in out
