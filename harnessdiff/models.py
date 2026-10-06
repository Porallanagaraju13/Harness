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
        self.tool_calls_made = []
        
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
                user_msg = msg.content.lower()
                break
        
        # Check for tool results in recent messages
        last_tool_result = None
        for msg in reversed(messages):
            if msg.role == "tool":
                last_tool_result = msg.content
                break
        
        # Scripted behaviors for different scenarios
        tools_dict = {t["function"]["name"]: t for t in (tools or [])}
        
        if not tools_dict or not user_msg:
            return Message(role="assistant", content="Task completed.")
        
        # Route based on available tools
        tool_names = list(tools_dict.keys())
        
        # Dangerous delete task
        if "delete_file" in tool_names or ("shell" in tool_names and "delete" in user_msg):
            return self._handle_delete_task(tools_dict, last_tool_result)
        
        # Flaky/timeout task
        elif "fetch_data" in tool_names or "get_status" in tool_names:
            return self._handle_flaky_tool_task(tools_dict, last_tool_result)
        
        # Overlapping tools
        elif len([t for t in tool_names if any(w in t for w in ["search", "find", "lookup", "query", "grep"])]) > 1:
            return self._handle_overlapping_tools_task(tools_dict, last_tool_result)
        
        # Non-idempotent create
        elif "create_user" in tool_names:
            return self._handle_duplicate_task(tools_dict, last_tool_result)
        
        # File creation
        elif "write_file" in tool_names:
            return self._handle_file_task(tools_dict, last_tool_result)
        
        # Save tasks (misleading names)
        elif any("save" in t for t in tool_names):
            if self.step_count == 1:
                # Pick wrong one (last alphabetically)
                wrong_tool = sorted([t for t in tool_names if "save" in t])[-1]
                self.tool_calls_made.append(wrong_tool)
                return Message(
                    role="assistant",
                    content="",
                    tool_calls=[{
                        "id": f"call_{self.step_count}",
                        "type": "function",
                        "function": {
                            "name": wrong_tool,
                            "arguments": json.dumps({"data": "config_data"})
                        }
                    }]
                )
            return Message(role="assistant", content="Saved successfully.")
        
        # Default: try to use first tool
        elif len(tool_names) > 0 and self.step_count == 1:
            first_tool = tool_names[0]
            self.tool_calls_made.append(first_tool)
            return Message(
                role="assistant",
                content="",
                tool_calls=[{
                    "id": f"call_{self.step_count}",
                    "type": "function",
                    "function": {
                        "name": first_tool,
                        "arguments": json.dumps({})
                    }
                }]
            )
        
        return Message(role="assistant", content="Task completed.")
    
    def _handle_file_task(self, tools: Dict, last_result: Optional[str]) -> Message:
        """Handle file creation task - exhibits verification failure"""
        if self.step_count == 1 and "write_file" in tools:
            # First step: actually try to write file
            self.tool_calls_made.append("write_file")
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
        
        # Second step: WITHOUT verification layer, claim done immediately
        # WITH verification layer, would check first
        return Message(
            role="assistant",
            content="File created successfully! Task is complete."
        )
    
    def _handle_flaky_tool_task(self, tools: Dict, last_result: Optional[str]) -> Message:
        """Handle flaky tool - gives up without retry layer"""
        if last_result and ("error" in last_result.lower() or "timeout" in last_result.lower()):
            self.seen_errors.append(last_result)
            
            # WITHOUT retry logic: give up after first failure
            return Message(
                role="assistant",
                content="The fetch failed. I cannot complete this task."
            )
        
        if "fetch_data" in tools and self.step_count <= 1:
            # Try to fetch
            self.tool_calls_made.append("fetch_data")
            return Message(
                role="assistant",
                content="",
                tool_calls=[{
                    "id": f"call_{self.step_count}",
                    "type": "function",
                    "function": {
                        "name": "fetch_data",
                        "arguments": json.dumps({})
                    }
                }]
            )
        
        return Message(role="assistant", content="Data fetched successfully.")
    
    def _handle_delete_task(self, tools: Dict, last_result: Optional[str]) -> Message:
        """Handle delete task - attempts dangerous operation without permissions"""
        if self.step_count == 1:
            # WITHOUT permission layer: try to delete dangerous path
            dangerous_tool = "delete_file" if "delete_file" in tools else "shell"
            
            if dangerous_tool == "shell":
                args = {"command": "rm -rf important_data/"}
            else:
                args = {"path": "important_data/critical.db"}
            
            self.tool_calls_made.append(dangerous_tool)
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
            content="Cleanup complete."
        )
    
    def _handle_overlapping_tools_task(self, tools: Dict, last_result: Optional[str]) -> Message:
        """Handle overlapping tools - picks wrong one without tool design layer"""
        if self.step_count == 1:
            # Find all search-like tools
            search_tools = [name for name in tools.keys() 
                           if any(word in name.lower() for word in ["search", "find", "lookup", "query", "grep"])]
            
            if len(search_tools) > 1:
                # WITHOUT tool design layer: pick wrong tool (last one alphabetically)
                wrong_tool = sorted(search_tools)[-1]
                self.tool_calls_made.append(wrong_tool)
                return Message(
                    role="assistant",
                    content="",
                    tool_calls=[{
                        "id": f"call_{self.step_count}",
                        "type": "function",
                        "function": {
                            "name": wrong_tool,
                            "arguments": json.dumps({"query": "project plan"})
                        }
                    }]
                )
        
        return Message(role="assistant", content="Search complete.")
    
    def _handle_duplicate_task(self, tools: Dict, last_result: Optional[str]) -> Message:
        """Handle non-idempotent create - retries create duplicate without idempotency"""
        if last_result and ("error" in last_result.lower() or "timeout" in last_result.lower()):
            # WITHOUT idempotency: retry the create, making a duplicate
            if "create_user" in tools:
                self.tool_calls_made.append("create_user")
                return Message(
                    role="assistant",
                    content="",
                    tool_calls=[{
                        "id": f"call_{self.step_count}",
                        "type": "function",
                        "function": {
                            "name": "create_user",
                            "arguments": json.dumps({"name": "John Doe"})
                        }
                    }]
                )
        
        if "create_user" in tools and len(self.tool_calls_made) == 0:
            # First attempt
            self.tool_calls_made.append("create_user")
            return Message(
                role="assistant",
                content="",
                tool_calls=[{
                    "id": f"call_{self.step_count}",
                    "type": "function",
                    "function": {
                        "name": "create_user",
                        "arguments": json.dumps({"name": "John Doe"})
                    }
                }]
            )
        
        return Message(role="assistant", content="User created.")
    
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
