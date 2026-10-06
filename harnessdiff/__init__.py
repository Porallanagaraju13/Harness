"""
HarnessDiff: A lab that shows exactly what each agent harness layer fixes.

Inspired by "Understanding Harness Engineering" by @techNmak
"""

__version__ = "1.0.0"

from harnessdiff.agent_loop import AgentLoop, Step, Trace
from harnessdiff.config import HarnessConfig
from harnessdiff.models import (
    DEFAULT_GEMINI_MODEL,
    GeminiModel,
    MockModel,
    ModelProvider,
    create_model,
)

__all__ = [
    "AgentLoop",
    "Step",
    "Trace",
    "ModelProvider",
    "MockModel",
    "GeminiModel",
    "HarnessConfig",
    "DEFAULT_GEMINI_MODEL",
    "create_model",
    "__version__",
]
