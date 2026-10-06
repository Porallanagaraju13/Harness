"""
HarnessDiff: A lab that shows exactly what each agent harness layer fixes.

Inspired by "Understanding Harness Engineering" by @techNmak
"""

__version__ = "0.1.0"

from harnessdiff.agent_loop import AgentLoop, Step, Trace
from harnessdiff.models import ModelProvider, MockModel
from harnessdiff.config import HarnessConfig

__all__ = [
    "AgentLoop",
    "Step",
    "Trace",
    "ModelProvider",
    "MockModel",
    "HarnessConfig",
]
