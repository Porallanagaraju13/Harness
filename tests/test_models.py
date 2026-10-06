"""Tests for models"""

from harnessdiff.models import MockModel, Message


def test_mock_model_basic():
    """Test mock model can generate responses"""
    model = MockModel()
    
    messages = [
        Message(role="user", content="Create a file output.txt")
    ]
    
    response = model.generate(messages)
    
    assert response.role == "assistant"
    assert response.content or response.tool_calls


def test_mock_model_file_creation():
    """Test mock model handles file creation scenario"""
    model = MockModel(failure_mode="verification")
    
    messages = [
        Message(role="user", content="Create a file with content 'test'")
    ]
    
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
                        "content": {"type": "string"}
                    }
                }
            }
        }
    ]
    
    response = model.generate(messages, tools=tools)
    
    # Should request tool call
    assert response.tool_calls or response.content


def test_mock_model_token_estimate():
    """Test mock model token estimation"""
    model = MockModel()
    
    text = "Hello " * 100
    tokens = model.estimate_tokens(text)
    
    # Should be roughly len(text) / 4
    assert tokens > 0
    assert tokens < len(text)


def test_mock_model_deterministic():
    """Test mock model is deterministic with same seed"""
    model1 = MockModel(seed=42)
    model2 = MockModel(seed=42)
    
    messages = [Message(role="user", content="Test")]
    
    response1 = model1.generate(messages)
    response2 = model2.generate(messages)
    
    # Should produce same response
    assert response1.content == response2.content
