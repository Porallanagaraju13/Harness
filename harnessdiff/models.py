"""
Model providers: deterministic mock and real LLM backends.

Chapter 1 of the handbook: "A model call is not an agent"
The model supplies learned capability; the harness determines how it's used.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
import os
import random
import urllib.error
import urllib.request

# Confirmed from the owner's live Gemini models API
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


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
        self.task_context = {}  # Track per-task state
        
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
            # Context management layer adds "[Context compacted... IMPORTANT: Your original goal was: ...]"
            has_goal_reminder = any(m.role == "system" and "original goal" in m.content.lower() for m in messages[-5:])
            if not has_goal_reminder:
                # Lost the original goal, give up early
                # This simulates losing track after reading a few files
                self.task_context["gave_up_from_overflow"] = True
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
            
            # For context overflow task, continue reading files until we lose track
            if "list_files" in last_tool_result.lower() and "read_file" in tools_dict:
                # After listing, start reading files
                # Track how many we've read
                if "files_read" not in self.task_context:
                    self.task_context["files_read"] = 0
                
                # Read a few files before potentially giving up from context overflow
                if self.task_context["files_read"] < 5:
                    file_num = self.task_context["files_read"]
                    self.task_context["files_read"] += 1
                    return Message(
                        role="assistant",
                        content="",
                        tool_calls=[{
                            "id": f"call_{self.step_count}",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": json.dumps({"name": f"file{file_num}.txt"})
                            }
                        }]
                    )
            elif "file" in last_tool_result.lower() and "bytes" in last_tool_result.lower() and "read_file" in tools_dict:
                # Continue reading more files in context overflow task
                if "files_read" not in self.task_context:
                    self.task_context["files_read"] = 0
                
                if self.task_context["files_read"] < 25:
                    file_num = self.task_context["files_read"]
                    self.task_context["files_read"] += 1
                    return Message(
                        role="assistant",
                        content="",
                        tool_calls=[{
                            "id": f"call_{self.step_count}",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": json.dumps({"name": f"file{file_num}.txt"})
                            }
                        }]
                    )
            
            # For multi-step verify task, need to read back after write
            if "wrote" in last_tool_result.lower() and "read_file" in tools_dict:
                # Task wants us to read back to confirm - do that
                return Message(
                    role="assistant",
                    content="",
                    tool_calls=[{
                        "id": f"call_{self.step_count}",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"path": "data.txt"})
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
        
        # Special handling for tasks with overlapping tools
        # At baseline (many overlapping tools), pick wrong one first to show confusion
        # With tool design layer (filtered tools), picks right one
        matching_tools = []
        for tool_name in tools_dict.keys():
            tool_info = tools_dict[tool_name]
            tool_desc = tool_info["function"].get("description", "").lower()
            tool_name_lower = tool_name.lower()
            
            # Check if tool matches task
            if any(kw in tool_name_lower or kw in tool_desc for kw in task_keywords):
                matching_tools.append((tool_name, tool_info))
        
        # Also check for overlapping search-like tools in the full tool set
        # (they might not match our keywords but are clearly overlapping)
        all_search_like = [t for t in tools_dict.items() if t[0] in ["search", "find", "lookup", "query", "grep"]]
        
        if not matching_tools and not all_search_like:
            # No matching tool found
            return Message(
                role="assistant",
                content="I don't have the right tool for this task."
            )
        
        # If we have many overlapping search-like tools available, this causes confusion
        if len(all_search_like) > 3 and ("search" in user_msg.lower() or "find" in user_msg.lower()):
            # With many overlapping search tools, pick a less optimal one (not "search")
            # Tool design layer will filter these, leaving only the best one
            # Pick "find" or "lookup" instead of "search"
            non_optimal = [t for t in all_search_like if t[0] != "search"]
            if non_optimal:
                tool_name, tool_info = non_optimal[0]
            else:
                # Fallback
                tool_name, tool_info = all_search_like[0]
        elif matching_tools:
            # Pick first matching tool
            tool_name, tool_info = matching_tools[0]
        else:
            # Use first search-like tool
            tool_name, tool_info = all_search_like[0]
        
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
            keywords.append("write")  # Save implies write
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
                # Extract specific filename from task if mentioned
                # Look for patterns like "file 'name.txt'" or "file \"name.txt\""
                import re
                file_match = re.search(r"file ['\"]([^'\"]+)['\"]", task)
                if file_match:
                    args[param] = file_match.group(1)
                # For backup tasks, try to write to /tmp/ (sandbox should block)
                elif "backup" in task and "/tmp/" in task:
                    args[param] = "/tmp/backup.txt"
                else:
                    args[param] = "output.txt"
            elif param == "content" or param == "data":
                # Extract specific content from task if mentioned
                # Look for patterns like "with 'content'" or "with \"content\""
                import re
                content_match = re.search(r"with ['\"]([^'\"]+)['\"]", task)
                if content_match:
                    args[param] = content_match.group(1)
                elif "backup" in task:
                    args[param] = "settings backup"
                else:
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


class GeminiModel(ModelProvider):
    """
    Google Gemini provider via the OpenAI-compatible endpoint.

    Default model id: gemini-3.8-flash (override with HARNESSDIFF_GEMINI_MODEL
    or --model gemini:<id>). Requires GEMINI_API_KEY.
    """

    DEFAULT_MODEL = DEFAULT_GEMINI_MODEL

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: str = GEMINI_OPENAI_BASE,
    ):
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Export it before using Gemini, "
                "or use --model mock for offline runs."
            )

        self.model = (
            model
            or os.getenv("HARNESSDIFF_GEMINI_MODEL")
            or self.DEFAULT_MODEL
        )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") + "/"

        try:
            import openai
        except ImportError:
            raise ImportError("Install openai: pip install 'harnessdiff[llm]'")

        self.client = openai.OpenAI(api_key=api_key, base_url=self.base_url)

    def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> Message:
        """Call Gemini via the OpenAI-compatible chat completions API."""
        msgs = []
        for msg in messages:
            m: Dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
            if msg.tool_calls:
                m["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            if msg.name:
                m["name"] = msg.name
            msgs.append(m)

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": msgs,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools

        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        return Message(
            role="assistant",
            content=choice.message.content or "",
            tool_calls=tool_calls,
        )

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4


def list_gemini_models(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List Gemini models from the Generative Language API.

    Returns a list of dicts with id, display_name, and supported methods.
    Raises ValueError if GEMINI_API_KEY is missing.
    """
    api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set. Cannot list Gemini models without a key."
        )

    url = f"{GEMINI_API_BASE}/models?key={api_key}&pageSize=100"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini models API error {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini models API unreachable: {exc}") from exc

    models = []
    for item in payload.get("models", []):
        name = item.get("name", "")
        model_id = name.split("/", 1)[-1] if name else ""
        if not model_id:
            continue
        methods = item.get("supportedGenerationMethods") or []
        models.append(
            {
                "id": model_id,
                "display_name": item.get("displayName") or model_id,
                "supported_methods": methods,
                "description": item.get("description") or "",
            }
        )
    models.sort(key=lambda m: m["id"])
    return models


def create_model(spec: str = "mock") -> ModelProvider:
    """
    Create a model provider from a CLI-style spec.

    Specs:
      mock
      openai[:model]
      anthropic[:model]
      gemini[:model]
    """
    name, _, model_id = spec.partition(":")
    name = name.strip().lower()
    model_id = model_id.strip() or None

    if name == "mock":
        return MockModel()
    if name == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        return OpenAIModel(model=model_id or "gpt-4o-mini", api_key=api_key)
    if name == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        return AnthropicModel(
            model=model_id or "claude-3-5-sonnet-20241022",
            api_key=api_key,
        )
    if name == "gemini":
        return GeminiModel(model=model_id)
    raise ValueError(
        f"Unknown model '{spec}'. Use mock, openai[:id], anthropic[:id], "
        f"or gemini[:id] (default Gemini id: {DEFAULT_GEMINI_MODEL})."
    )
