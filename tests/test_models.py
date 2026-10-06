"""Tests for models"""

import json
from unittest.mock import MagicMock, patch

import pytest

from harnessdiff.models import (
    DEFAULT_GEMINI_MODEL,
    GeminiModel,
    Message,
    MockModel,
    create_model,
    list_gemini_models,
)


def test_mock_model_basic():
    """Test mock model can generate responses"""
    model = MockModel()

    messages = [Message(role="user", content="Create a file output.txt")]

    response = model.generate(messages)

    assert response.role == "assistant"
    assert response.content or response.tool_calls


def test_mock_model_file_creation():
    """Test mock model handles file creation scenario"""
    model = MockModel()

    messages = [Message(role="user", content="Create a file with content 'test'")]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                },
            },
        }
    ]

    response = model.generate(messages, tools=tools)

    assert response.tool_calls or response.content


def test_mock_model_token_estimate():
    """Test mock model token estimation"""
    model = MockModel()

    text = "Hello " * 100
    tokens = model.estimate_tokens(text)

    assert tokens > 0
    assert tokens < len(text)


def test_mock_model_deterministic():
    """Test mock model is deterministic with same seed"""
    model1 = MockModel(seed=42)
    model2 = MockModel(seed=42)

    messages = [Message(role="user", content="Test")]

    response1 = model1.generate(messages)
    response2 = model2.generate(messages)

    assert response1.content == response2.content


def test_default_gemini_model_id():
    """Default Gemini model must be gemini-3.8-flash"""
    assert DEFAULT_GEMINI_MODEL == "gemini-3.8-flash"


def test_create_model_mock():
    model = create_model("mock")
    assert isinstance(model, MockModel)


def test_gemini_requires_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiModel()


def test_gemini_default_model_from_constant(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("HARNESSDIFF_GEMINI_MODEL", raising=False)

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value = MagicMock()
        model = GeminiModel()
        assert model.model == "gemini-3.8-flash"
        mock_openai.assert_called_once()
        kwargs = mock_openai.call_args.kwargs
        assert "generativelanguage.googleapis.com" in kwargs["base_url"]


def test_gemini_env_model_override(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("HARNESSDIFF_GEMINI_MODEL", "gemini-flash-latest")

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value = MagicMock()
        model = create_model("gemini")
        assert isinstance(model, GeminiModel)
        assert model.model == "gemini-flash-latest"


def test_gemini_cli_spec_override(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value = MagicMock()
        model = create_model("gemini:gemini-3.8-flash")
        assert model.model == "gemini-3.8-flash"


def test_gemini_generate_mocked_http(monkeypatch):
    """Gemini generate uses OpenAI-compatible client; mock the response."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    mock_choice = MagicMock()
    mock_choice.message.content = "Hello from Gemini"
    mock_choice.message.tool_calls = None

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        model = GeminiModel(model="gemini-3.8-flash")
        result = model.generate([Message(role="user", content="hi")])

    assert result.content == "Hello from Gemini"
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gemini-3.8-flash"


def test_list_gemini_models_mocked(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    payload = {
        "models": [
            {
                "name": "models/gemini-3.8-flash",
                "displayName": "Gemini 3.8 Flash",
                "supportedGenerationMethods": ["generateContent"],
                "description": "Fast",
            },
            {
                "name": "models/gemini-flash-latest",
                "displayName": "Gemini Flash Latest",
                "supportedGenerationMethods": ["generateContent"],
            },
        ]
    }

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        models = list_gemini_models()

    ids = [m["id"] for m in models]
    assert "gemini-3.8-flash" in ids
    assert "gemini-flash-latest" in ids


def test_list_gemini_models_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        list_gemini_models()
