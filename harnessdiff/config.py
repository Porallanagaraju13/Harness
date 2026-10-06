"""
Configuration for harness layers and execution.

See Section 3 of "Understanding Harness Engineering" - what the harness controls.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class HarnessConfig:
    """
    Configuration for all harness layers.

    Each layer can be independently enabled/disabled to measure its impact.
    Based on the harness responsibilities outlined in Chapter 3 of the handbook.
    """

    # Tool Design Layer (Chapters 5-10)
    use_distinct_tools: bool = False
    """Use well-designed, distinct tools vs overlapping/vague ones"""

    # Context Management Layer (Chapters 12-15)
    use_context_management: bool = False
    """Apply context selection and compaction strategies"""
    max_context_tokens: int = 8000
    """Maximum tokens in context before compaction"""

    # Sandbox Layer (Chapters 18-19)
    use_sandbox: bool = False
    """Execute tools in isolated sandbox environment"""
    sandbox_work_dir: Optional[Path] = None
    """Isolated working directory for sandbox"""

    # Permission/Approval Layer (Chapters 20-22)
    use_permissions: bool = False
    """Enable permission checks and approval for risky actions"""
    policy_file: Optional[Path] = None
    """Path to permission policy file"""
    auto_deny_dangerous: bool = True
    """Auto-deny dangerous operations (vs simulated approval)"""

    # Retry/Idempotency Layer (Chapters 29-31)
    use_retry_logic: bool = False
    """Enable retries with idempotency tracking"""
    max_retries: int = 3
    """Maximum retry attempts per operation"""

    # Verification Layer (Chapters 25-28)
    use_verification: bool = False
    """Use independent verifier instead of trusting agent claims"""

    # Long-running/Checkpoint Layer (optional, Chapter 29)
    use_checkpoints: bool = False
    """Enable checkpoint/resume for long-running tasks"""
    checkpoint_dir: Optional[Path] = None
    """Directory for checkpoint state"""

    # Budget constraints (Chapter 24)
    max_steps: int = 50
    """Maximum agent steps before termination"""
    max_tool_calls: int = 100
    """Maximum tool calls allowed"""

    # Logging
    trace_file: Optional[Path] = None
    """Path to JSONL trace output"""
    verbose: bool = False
    """Enable verbose output"""

    def __post_init__(self):
        """Convert string paths to Path objects"""
        if isinstance(self.sandbox_work_dir, str):
            self.sandbox_work_dir = Path(self.sandbox_work_dir)
        if isinstance(self.policy_file, str):
            self.policy_file = Path(self.policy_file)
        if isinstance(self.checkpoint_dir, str):
            self.checkpoint_dir = Path(self.checkpoint_dir)
        if isinstance(self.trace_file, str):
            self.trace_file = Path(self.trace_file)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization"""
        result = {}
        for k, v in self.__dict__.items():
            if isinstance(v, Path):
                result[k] = str(v)
            else:
                result[k] = v
        return result

    @classmethod
    def baseline(cls) -> "HarnessConfig":
        """Configuration with NO harness layers (before)"""
        return cls(
            use_distinct_tools=False,
            use_context_management=False,
            use_sandbox=False,
            use_permissions=False,
            use_retry_logic=False,
            use_verification=False,
        )

    @classmethod
    def full_harness(cls) -> "HarnessConfig":
        """Configuration with ALL harness layers (after)"""
        return cls(
            use_distinct_tools=True,
            use_context_management=True,
            use_sandbox=True,
            use_permissions=True,
            use_retry_logic=True,
            use_verification=True,
        )

    def enable_layer(self, layer_name: str) -> "HarnessConfig":
        """Create new config with specified layer enabled"""
        config = HarnessConfig(**self.to_dict())

        layer_map = {
            "tool_design": "use_distinct_tools",
            "context": "use_context_management",
            "sandbox": "use_sandbox",
            "permissions": "use_permissions",
            "retry": "use_retry_logic",
            "verification": "use_verification",
        }

        if layer_name not in layer_map:
            raise ValueError(f"Unknown layer: {layer_name}")

        setattr(config, layer_map[layer_name], True)
        return config
