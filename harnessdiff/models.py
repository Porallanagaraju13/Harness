"""
Model providers: deterministic mock and real LLM backends.

Chapter 1 of the handbook: "A model call is not an agent"
The model supplies learned capability; the harness determines how it's used.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
import random


@dataclass
class Message:
    """A message in the conversation"""
    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


@dataclass
class ToolCall:
    """A tool call request from the model"""
    id: str
    name: str
    arguments: Dict[str, Any]


class ModelProvider(ABC):
    """
    Abstract interface for language models.
    
    The harness calls the model but doesn't depend on a specific provider.
    """
    
    @abstractmethod
    def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> Message:
        """
        Generate a response given messages and available tools.
        
        Returns a Message that may contain text or tool calls.
        """
        pass
    
    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Rough token count estimate"""
        pass


class MockModel(ModelProvider):
    """
    Deterministic scripted model that exhibits classic failure modes.
    
    Failure modes (from Chapter 40):
    - Claims done when not done (verification failure)
    - Repeats non-idempotent side effects on retry (recovery failure)
    - Picks wrong tool among overlapping tools (tool-selection failure)
    - Runs destructive command (authorization failure)
    - Loses track after context overflow (context failure)
    - Gives up on flaky tool (should retry)
    """
    
    def __init__(self, failure_mode: str = "all", seed: int = 42):
        """
        Args:
            failure_mode: Which failure to exhibit
            seed: Random seed for deterministic behavior
        """
        self.failure_mode = failure_mode
        self.step_count = 0
        self.random = random.Random(seed)
        self.seen_errors = []
        self.idempotency_keys = set()
        
    def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> Message:
        """Generate deterministic response based on context"""
        self.step_count += 1
        
        # Extract user intent from messages
        user_msg = None
        for msg in reversed(messages):
            if msg.role == "user":
                user_msg = msg.content
                break
        
        # Check for tool results in recent messages
        last_tool_result = None
        for msg in reversed(messages):
            if msg.role == "tool":
                last_tool_result = msg.content
                break
        
        # Scripted behaviors for different scenarios
        tools_dict = {t["function"]["name"]: t for t in (tools or [])}
        
        # Handle different task types
        if user_msg and "file" in user_msg.lower() and "create" in user_msg.lower():
            return self._handle_file_creation(tools_dict, last_tool_result)
        
        elif user_msg and "test" in user_msg.lower():
            return self._handle_test_task(tools_dict, last_tool_result)
        
        elif user_msg and "delete" in user_msg.lower():
            return self._handle_delete_task(tools_dict, last_tool_result)
        
        elif user_msg and "search" in user_msg.lower():
            return self._handle_search_task(tools_dict, last_tool_result)
        
        else:
            # Default: claim done prematurely
            return Message(
                role="assistant",
                content="Task completed successfully!"
            )
    
    def _handle_file_creation(self, tools: Dict, last_result: Optional[str]) -> Message:
        """Handle file creation task - exhibits verification failure"""
        if self.step_count == 1:
            # First step: try to write file
            if "write_file" in tools:
                return Message(
                    role="assistant",
                    content="",
                    tool_calls=[{
                        "id": f"call_{self.step_count}",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": json.dumps({
                                "path": "output.txt",
                                "content": "Hello World"
                            })
                        }
                    }]
                )
        
        # Second step: claim done WITHOUT verifying
        if self.failure_mode in ["all", "verification"]:
            return Message(
                role="assistant",
                content="File created successfully! Task is complete."
            )
        else:
            return Message(
                role="assistant",
                content="Let me verify the file was created."
            )
    
    def _handle_test_task(self, tools: Dict, last_result: Optional[str]) -> Message:
        """Handle test task - exhibits retry issues"""
        if last_result and "error" in last_result.lower():
            self.seen_errors.append(last_result)
            
            # Without retry logic: give up
            if self.failure_mode in ["all", "retry"] and len(self.seen_errors) == 1:
                return Message(
                    role="assistant",
                    content="The test failed. I cannot complete this task."
                )
        
        if "run_tests" in tools:
            # Attempt to run tests (might be non-idempotent without key)
            return Message(
                role="assistant",
                content="",
                tool_calls=[{
                    "id": f"call_{self.step_count}",
                    "type": "function",
                    "function": {
                        "name": "run_tests",
                        "arguments": json.dumps({})
                    }
                }]
            )
        
        return Message(role="assistant", content="Tests complete.")
    
    def _handle_delete_task(self, tools: Dict, last_result: Optional[str]) -> Message:
        """Handle delete task - exhibits authorization failure"""
        # Try to delete without checking permissions
        if "delete_file" in tools or "shell" in tools:
            dangerous_tool = "delete_file" if "delete_file" in tools else "shell"
            
            if dangerous_tool == "shell":
                args = {"command": "rm -rf important_data/"}
            else:
                args = {"path": "important_data/critical.db"}
            
            return Message(
                role="assistant",
                content="",
                tool_calls=[{
                    "id": f"call_{self.step_count}",
                    "type": "function",
                    "function": {
                        "name": dangerous_tool,
                        "arguments": json.dumps(args)
                    }
                }]
            )
        
        return Message(
            role="assistant",
            content="Cannot complete delete operation."
        )
    
    def _handle_search_task(self, tools: Dict, last_result: Optional[str]) -> Message:
        """Handle search task - exhibits tool selection failure with overlapping tools"""
        # If multiple overlapping tools exist, pick wrong one
        search_tools = [name for name in tools.keys() 
                       if any(word in name for word in ["search", "find", "lookup", "query"])]
        
        if len(search_tools) > 1 and self.failure_mode in ["all", "tool_selection"]:
            # Pick a less appropriate tool
            wrong_tool = search_tools[-1]  # Arbitrary wrong choice
            return Message(
                role="assistant",
                content="",
                tool_calls=[{
                    "id": f"call_{self.step_count}",
                    "type": "function",
                    "function": {
                        "name": wrong_tool,
                        "arguments": json.dumps({"query": "test"})
                    }
                }]
            )
        elif search_tools:
            # Use first available search tool
            return Message(
                role="assistant",
                content="",
                tool_calls=[{
                    "id": f"call_{self.step_count}",
                    "type": "function",
                    "function": {
                        "name": search_tools[0],
                        "arguments": json.dumps({"query": "test"})
                    }
                }]
            )
        
        return Message(
            role="assistant",
            content="Search complete."
        )
    
    def estimate_tokens(self, text: str) -> int:
        """Rough estimate: ~4 chars per token"""
        return len(text) // 4


class OpenAIModel(ModelProvider):
    """OpenAI-compatible API provider"""
    
    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None):
        try:
            import openai
        except ImportError:
            raise ImportError("Install openai: pip install 'harnessdiff[llm]'")
        
        self.model = model
        self.client = openai.OpenAI(api_key=api_key)
    
    def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> Message:
        """Call OpenAI API"""
        import openai
        
        msgs = []
        for msg in messages:
            m = {"role": msg.role, "content": msg.content or ""}
            if msg.tool_calls:
                m["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            if msg.name:
                m["name"] = msg.name
            msgs.append(m)
        
        kwargs = {"model": self.model, "messages": msgs, "temperature": temperature}
        if tools:
            kwargs["tools"] = tools
        
        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        
        return Message(
            role="assistant",
            content=choice.message.content or "",
            tool_calls=choice.message.tool_calls
        )
    
    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4


class AnthropicModel(ModelProvider):
    """Anthropic Claude API provider"""
    
    def __init__(self, model: str = "claude-3-5-sonnet-20241022", api_key: Optional[str] = None):
        try:
            import anthropic
        except ImportError:
            raise ImportError("Install anthropic: pip install 'harnessdiff[llm]'")
        
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key)
    
    def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> Message:
        """Call Anthropic API"""
        # Convert messages to Anthropic format
        system_msgs = [m.content for m in messages if m.role == "system"]
        system = "\n\n".join(system_msgs) if system_msgs else None
        
        msgs = []
        for msg in messages:
            if msg.role in ["user", "assistant"]:
                msgs.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": msgs,
            "temperature": temperature
        }
        if system:
            kwargs["system"] = system
        if tools:
            # Convert to Anthropic tool format
            kwargs["tools"] = tools
        
        response = self.client.messages.create(**kwargs)
        
        # Extract content
        content = ""
        tool_calls = []
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text
            elif hasattr(block, "tool_use"):
                tool_calls.append({
                    "id": block.tool_use.id,
                    "type": "function",
                    "function": {
                        "name": block.tool_use.name,
                        "arguments": json.dumps(block.tool_use.input)
                    }
                })
        
        return Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls if tool_calls else None
        )
    
    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4
