"""Tests for core agent loop"""

import tempfile
from pathlib import Path

from harnessdiff.agent_loop import AgentLoop, Step, Trace
from harnessdiff.config import HarnessConfig
from harnessdiff.models import MockModel


def test_step_serialization():
    """Test Step can be serialized"""
    step = Step(
        step_num=1,
        timestamp=123.456,
        messages=[{"role": "user", "content": "test"}],
        action={"type": "final"},
        observation="done",
    )

    data = step.to_dict()
    assert data["step_num"] == 1
    assert data["timestamp"] == 123.456


def test_trace_to_jsonl():
    """Test Trace can be converted to JSONL"""
    trace = Trace(task_id="test", config={"test": True})

    step = Step(step_num=1, timestamp=123.0, messages=[])
    trace.steps.append(step)
    trace.result = {"status": "completed"}
    trace.end_time = 124.0

    lines = trace.to_jsonl()
    assert len(lines) == 3  # header, step, result
    assert "trace_start" in lines[0]
    assert "step" in lines[1]
    assert "trace_end" in lines[2]


def test_trace_save():
    """Test Trace can be saved to file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        trace_file = Path(tmpdir) / "trace.jsonl"

        trace = Trace(task_id="test", config={})
        trace.result = {"status": "completed"}
        trace.end_time = 123.0

        trace.save(trace_file)

        assert trace_file.exists()
        content = trace_file.read_text()
        assert "trace_start" in content


def test_agent_loop_basic():
    """Test basic agent loop execution"""
    model = MockModel()

    # Simple tool
    def echo(message: str) -> str:
        return f"Echo: {message}"

    tools = {"echo": echo}
    tool_schemas = [
        {
            "type": "function",
            "function": {
                "name": "echo",
                "description": "Echo a message",
                "parameters": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
            },
        }
    ]

    config = HarnessConfig(max_steps=10)

    agent = AgentLoop(model=model, tools=tools, config=config, tool_schemas=tool_schemas)

    trace = agent.run("Say hello", task_id="test")

    assert trace.task_id == "test"
    assert trace.result is not None
    assert len(trace.steps) > 0


def test_agent_loop_with_budget():
    """Test agent loop respects budget limits"""
    model = MockModel()

    def infinite_loop() -> str:
        return "continue"

    config = HarnessConfig(max_steps=3)

    agent = AgentLoop(model=model, tools={"infinite": infinite_loop}, config=config)

    trace = agent.run("Keep going forever", task_id="test")

    # Should stop at max_steps
    assert len(trace.steps) <= config.max_steps
