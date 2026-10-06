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
    Environment-reactive policy model that responds to what it sees.
    
    Key behaviors:
    - Picks first keyword-matching tool (helped by distinct tool design)
    - Claims done after apparent main step (caught by verifier feedback)
    - Reaches for destructive commands on cleanup (blocked by permissions)
    - Gives up after first error (helped by retry layer)
    - Only sees recent context (helped by context management)
    
    The harness changes what the model sees, which changes what it does.
    """
    
    def __init__(self, seed: int = 42):
        self.step_count = 0
        self.random = random.Random(seed)
        
    def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> Message:
        """Generate response by reacting to current context"""
        self.step_count += 1
        
        # Extract recent context
        user_msg = None
        last_tool_result = None
        initial_goal = None
        
        for msg in reversed(messages):
            if msg.role == "user" and not user_msg:
                user_msg = msg.content.lower()
            if msg.role == "tool" and not last_tool_result:
                last_tool_result = msg.content
        
        # Check if we've lost the original goal (context overflow without compaction)
        # In real context overflow, messages list is huge and original prompt is far away
        if len(messages) > 15:  # Arbitrary threshold for "lost in context"
            # Check if we can still see the original goal
            has_system_summary = any(m.role == "system" and "goal" in m.content.lower() for m in messages[-5:])
            if not has_system_summary:
                # Lost the original goal, give up
                return Message(
                    role="assistant",
                    content="I've lost track of what I was supposed to do. Too much context."
                )
        
        if not user_msg:
            return Message(role="assistant", content="No task.")
        
        tools_dict = {t["function"]["name"]: t for t in (tools or [])}
        
        # React to tool results
        if last_tool_result:
            # If we see an error, give up (unless retry layer retries transparently)
            if any(word in last_tool_result.lower() for word in ["error", "timeout", "failed", "exception"]):
                return Message(
                    role="assistant",
                    content=f"The operation failed: {last_tool_result[:100]}. I cannot complete the task."
                )
            
            # If we see a permission denial with guidance, follow it
            if "permission denied" in last_tool_result.lower() and "use" in last_tool_result.lower():
                # Permission layer guided us to safer action
                # Try to extract suggested action
                return Message(
                    role="assistant",
                    content="I'll use the suggested safer approach."
                )
            
            # If we see verification failure with concrete feedback, try to fix
            if any(word in last_tool_result.lower() for word in ["missing", "not found", "wrong", "incorrect", "verification failed"]):
                # Verifier gave us concrete feedback
                if self.step_count < 5:  # Bounded fix attempts
                    # Extract what needs fixing from the feedback
                    if "write_file" in tools_dict:
                        # Try to fix the file issue
                        return Message(
                            role="assistant",
                            content="",
                            tool_calls=[{
                                "id": f"call_{self.step_count}_fix",
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
                    elif "read_file" in tools_dict:
                        # Try reading a different file
                        return Message(
                            role="assistant",
                            content="",
                            tool_calls=[{
                                "id": f"call_{self.step_count}_fix",
                                "type": "function",
                                "function": {
                                    "name": "read_file",
                                    "arguments": json.dumps({"name": "file25.txt"})
                                }
                            }]
                        )
            
            # Otherwise, assume success after tool execution
            return Message(
                role="assistant",
                content="Task completed successfully!"
            )
        
        # First step: pick tool based on keyword matching
        # Policy: pick FIRST tool whose name/description matches task keywords
        task_keywords = self._extract_keywords(user_msg)
        
        # Find matching tool
        for tool_name in tools_dict.keys():
            tool_info = tools_dict[tool_name]
            tool_desc = tool_info["function"].get("description", "").lower()
            tool_name_lower = tool_name.lower()
            
            # Check if tool matches task
            if any(kw in tool_name_lower or kw in tool_desc for kw in task_keywords):
                # Prepare arguments based on tool parameters
                args = self._prepare_args(tool_info, user_msg)
                
                return Message(
                    role="assistant",
                    content="",
                    tool_calls=[{
                        "id": f"call_{self.step_count}",
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(args)
                        }
                    }]
                )
        
        # No matching tool found
        return Message(
            role="assistant",
            content="I don't have the right tool for this task."
        )
    
    def _extract_keywords(self, task: str) -> List[str]:
        """Extract action keywords from task"""
        keywords = []
        
        # Action words
        if "create" in task or "write" in task:
            keywords.append("write")
            keywords.append("create")
        if "delete" in task or "remove" in task or "clean" in task:
            keywords.append("delete")
            keywords.append("remove")
            keywords.append("clean")
        if "fetch" in task or "get" in task or "retrieve" in task:
            keywords.append("fetch")
            keywords.append("get")
            keywords.append("retrieve")
        if "search" in task or "find" in task:
            keywords.append("search")
            keywords.append("find")
        if "save" in task:
            keywords.append("save")
        if "read" in task or "list" in task:
            keywords.append("read")
            keywords.append("list")
        if "status" in task or "monitor" in task:
            keywords.append("status")
            keywords.append("monitor")
        if "user" in task:
            keywords.append("user")
        if "shell" in task or "command" in task:
            keywords.append("shell")
        
        return keywords
    
    def _prepare_args(self, tool_info: Dict, task: str) -> Dict:
        """Prepare arguments for tool call based on task"""
        params = tool_info["function"].get("parameters", {})
        props = params.get("properties", {})
        required = params.get("required", [])
        
        args = {}
        
        # Fill in required arguments with reasonable defaults
        for param in required:
            if param in ["path", "file", "name"]:
                args[param] = "output.txt"
            elif param == "content" or param == "data":
                args[param] = "Hello World"
            elif param == "command":
                # For cleanup tasks, reach for destructive command first
                if "clean" in task or "delete" in task or "remove" in task:
                    args[param] = "rm -rf important_data/"
                else:
                    args[param] = "ls"
            elif param == "query":
                args[param] = "project plan"
        
        return args
    
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
