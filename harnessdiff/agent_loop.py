"""
Core agent loop implementation.

Chapter 2: "The minimal agent loop"
Task -> Context -> Model -> Action/Final -> Execute -> Observe -> Update state -> Continue
"""

import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from datetime import datetime

from harnessdiff.models import ModelProvider, Message
from harnessdiff.config import HarnessConfig


@dataclass
class Step:
    """
    A single step in the agent trace.
    
    Records the evolving state s_t, context c_t, action a_t, and observation o_t
    as described in Chapter 2.
    """
    step_num: int
    timestamp: float
    messages: List[Dict[str, Any]]  # Current context
    action: Optional[Dict[str, Any]] = None  # Tool call or final answer
    observation: Optional[str] = None  # Tool result
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSONL serialization"""
        return asdict(self)


@dataclass
class Trace:
    """
    Complete trace of an agent run.
    
    Provides the audit trail needed for debugging and evaluation.
    """
    task_id: str
    config: Dict[str, Any]
    steps: List[Step] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    def to_jsonl(self) -> List[str]:
        """Convert trace to JSONL lines"""
        lines = []
        
        # Header
        header = {
            "type": "trace_start",
            "task_id": self.task_id,
            "config": self.config,
            "start_time": self.start_time
        }
        lines.append(json.dumps(header))
        
        # Steps
        for step in self.steps:
            step_data = {"type": "step", **step.to_dict()}
            lines.append(json.dumps(step_data))
        
        # Result
        if self.result:
            result_data = {
                "type": "trace_end",
                "task_id": self.task_id,
                "result": self.result,
                "end_time": self.end_time
            }
            lines.append(json.dumps(result_data))
        
        return lines
    
    def save(self, path: Path):
        """Save trace to JSONL file"""
        with open(path, "w") as f:
            for line in self.to_jsonl():
                f.write(line + "\n")


class AgentLoop:
    """
    The core agent harness loop.
    
    Implements the control flow from Chapter 2:
    - Assemble active context
    - Model invocation
    - Final answer or action request?
    - Policy / approval / tool routing
    - Execute in environment
    - Observation + state update
    
    The harness controls what the model sees, which tools are available,
    how tools execute, when to stop, and how to verify completion.
    """
    
    def __init__(
        self,
        model: ModelProvider,
        tools: Dict[str, Callable],
        config: HarnessConfig,
        tool_schemas: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Args:
            model: The language model provider
            tools: Dictionary mapping tool names to callable functions
            config: Harness configuration
            tool_schemas: OpenAI-format tool schemas
        """
        self.model = model
        self.tools = tools
        self.config = config
        self.tool_schemas = tool_schemas or []
        
        # State
        self.messages: List[Message] = []
        self.step_count = 0
        self.tool_call_count = 0
        self.total_tokens = 0
        
        # Apply layers
        self._apply_layers()
    
    def _apply_layers(self):
        """Apply configured harness layers"""
        # Import layers here to avoid circular imports
        from harnessdiff.layers.tool_design import ToolDesignLayer
        from harnessdiff.layers.context_mgmt import ContextManagementLayer
        from harnessdiff.layers.sandbox import SandboxLayer
        from harnessdiff.layers.permissions import PermissionLayer
        from harnessdiff.layers.retry import RetryLayer
        from harnessdiff.layers.verification import VerificationLayer
        
        # Store layer instances for metrics collection
        self._permission_layer = None
        self._retry_layer = None
        
        # Wrap tools with layers
        if self.config.use_distinct_tools:
            tool_layer = ToolDesignLayer(self.config)
            self.tools = tool_layer.wrap_tools(self.tools)
            self.tool_schemas = tool_layer.improve_schemas(self.tool_schemas)
        
        if self.config.use_sandbox:
            sandbox_layer = SandboxLayer(self.config)
            self.tools = sandbox_layer.wrap_tools(self.tools)
        
        if self.config.use_permissions:
            perm_layer = PermissionLayer(self.config)
            self.tools = perm_layer.wrap_tools(self.tools)
            self._permission_layer = perm_layer  # Store for metrics
        
        if self.config.use_retry_logic:
            retry_layer = RetryLayer(self.config)
            self.tools = retry_layer.wrap_tools(self.tools)
            self._retry_layer = retry_layer  # Store for metrics
        
        # Context and verification are handled in the loop itself
        self.context_layer = None
        self.verification_layer = None
        
        if self.config.use_context_management:
            self.context_layer = ContextManagementLayer(self.config)
        
        if self.config.use_verification:
            self.verification_layer = VerificationLayer(self.config)
    
    def run(self, task_prompt: str, task_id: str = "task") -> Trace:
        """
        Run the agent loop on a task.
        
        Returns a complete trace of execution.
        """
        # Initialize trace
        trace = Trace(
            task_id=task_id,
            config=self.config.to_dict()
        )
        
        # Initialize messages
        system_msg = Message(
            role="system",
            content="You are a helpful assistant that completes tasks using available tools. "
                   "Use tools to accomplish the task and report completion when done."
        )
        user_msg = Message(role="user", content=task_prompt)
        
        self.messages = [system_msg, user_msg]
        self.step_count = 0
        self.tool_call_count = 0
        
        # Main loop
        try:
            while self.step_count < self.config.max_steps:
                step_result = self._execute_step(trace)
                
                if step_result == "final":
                    # Agent returned final answer
                    trace.result = {
                        "status": "completed",
                        "final_message": self.messages[-1].content,
                        "steps": self.step_count,
                        "tool_calls": self.tool_call_count
                    }
                    break
                elif step_result == "budget_exceeded":
                    trace.result = {
                        "status": "budget_exceeded",
                        "steps": self.step_count,
                        "tool_calls": self.tool_call_count
                    }
                    break
        
        except Exception as e:
            trace.result = {
                "status": "error",
                "error": str(e),
                "steps": self.step_count
            }
        
        trace.end_time = time.time()
        
        # Save trace if configured
        if self.config.trace_file:
            trace.save(self.config.trace_file)
        
        return trace
    
    def _execute_step(self, trace: Trace) -> str:
        """
        Execute a single step of the agent loop.
        
        Returns "continue", "final", or "budget_exceeded"
        """
        self.step_count += 1
        
        # Apply context management
        if self.context_layer:
            active_messages = self.context_layer.select_context(self.messages)
        else:
            active_messages = self.messages
        
        # Record step start
        step = Step(
            step_num=self.step_count,
            timestamp=time.time(),
            messages=[self._message_to_dict(m) for m in active_messages]
        )
        
        # Model invocation
        try:
            response = self.model.generate(
                messages=active_messages,
                tools=self.tool_schemas if self.tool_schemas else None,
                temperature=0.7
            )
        except Exception as e:
            step.observation = f"Model error: {e}"
            trace.steps.append(step)
            return "final"
        
        # Track tokens
        response_text = response.content or ""
        self.total_tokens += self.model.estimate_tokens(response_text)
        
        self.messages.append(response)
        
        # Check if final answer or tool call
        if response.tool_calls:
            # Execute tool calls
            step.action = {
                "type": "tool_calls",
                "calls": response.tool_calls
            }
            
            for tool_call in response.tool_calls:
                self.tool_call_count += 1
                
                if self.tool_call_count > self.config.max_tool_calls:
                    step.observation = "Tool call budget exceeded"
                    trace.steps.append(step)
                    return "budget_exceeded"
                
                # Execute tool
                result = self._execute_tool(tool_call)
                
                # Add tool result to messages
                tool_result_msg = Message(
                    role="tool",
                    content=result,
                    tool_call_id=tool_call["id"],
                    name=tool_call["function"]["name"]
                )
                self.messages.append(tool_result_msg)
                
                step.observation = result
            
            trace.steps.append(step)
            return "continue"
        
        else:
            # Final answer
            step.action = {"type": "final_answer", "content": response.content}
            trace.steps.append(step)
            return "final"
    
    def _execute_tool(self, tool_call: Dict[str, Any]) -> str:
        """Execute a tool call and return result"""
        tool_name = tool_call["function"]["name"]
        
        # Parse arguments
        try:
            args_str = tool_call["function"]["arguments"]
            if isinstance(args_str, str):
                args = json.loads(args_str)
            else:
                args = args_str
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON arguments: {e}"
        
        # Look up tool
        if tool_name not in self.tools:
            return f"Error: Tool '{tool_name}' not found"
        
        tool_fn = self.tools[tool_name]
        
        # Execute
        try:
            result = tool_fn(**args)
            return str(result)
        except Exception as e:
            return f"Error executing {tool_name}: {e}"
    
    def _message_to_dict(self, msg: Message) -> Dict[str, Any]:
        """Convert Message to dictionary"""
        result = {"role": msg.role, "content": msg.content}
        if msg.tool_calls:
            result["tool_calls"] = msg.tool_calls
        if msg.tool_call_id:
            result["tool_call_id"] = msg.tool_call_id
        if msg.name:
            result["name"] = msg.name
        return result
