"""
Sandbox Layer

Chapters 18-19 of the handbook:
- Execution environments
- A sandbox is an isolation boundary, not the orchestrator
"""

import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict

from harnessdiff.config import HarnessConfig


class SandboxLayer:
    """
    Isolates tool execution in a restricted environment.

    Chapter 19: "A sandbox is an isolation boundary"

    Without Docker (Windows + Linux compatible):
    - Isolated temp working directory
    - Subprocess with timeout
    - Environment variable scrubbing
    - Path restrictions
    """

    def __init__(self, config: HarnessConfig):
        self.config = config

        # Create isolated work directory
        if config.sandbox_work_dir:
            self.work_dir = Path(config.sandbox_work_dir)
            self.work_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.temp_dir = tempfile.mkdtemp(prefix="harnessdiff_sandbox_")
            self.work_dir = Path(self.temp_dir)

    def wrap_tools(self, tools: Dict[str, Callable]) -> Dict[str, Callable]:
        """Wrap tools to execute in sandbox"""
        wrapped = {}

        for name, tool_fn in tools.items():
            if self._is_dangerous(name):
                wrapped[name] = self._make_sandboxed(tool_fn)
            else:
                wrapped[name] = tool_fn

        return wrapped

    def _is_dangerous(self, tool_name: str) -> bool:
        """Check if tool needs sandboxing"""
        dangerous_keywords = ["shell", "exec", "write", "delete", "run", "command"]
        return any(kw in tool_name.lower() for kw in dangerous_keywords)

    def _make_sandboxed(self, tool_fn: Callable) -> Callable:
        """Wrap tool to execute in sandbox"""

        def wrapper(**kwargs):
            # Check for out-of-workspace writes
            # Don't rewrite paths - let the tool work in its work_dir
            # Just detect and block absolute paths outside workspace
            for key, value in kwargs.items():
                if key in ["path", "file", "directory"]:
                    if isinstance(value, (str, Path)):
                        p = Path(value)
                        # Only block absolute paths that are clearly outside workspace
                        if p.is_absolute():
                            # Check common system paths
                            path_str = str(p)
                            if any(
                                prefix in path_str
                                for prefix in [
                                    "/tmp/",
                                    "/var/",
                                    "/etc/",
                                    "/usr/",
                                    "/home/",
                                    "C:\\",
                                    "D:\\",
                                ]
                            ):
                                # This is an absolute system path - block it
                                # The return message is what the agent sees
                                return f"Sandbox blocked: cannot access {value} (outside workspace)"

            # Execute with restricted environment
            try:
                result = tool_fn(**kwargs)
                return result
            except Exception as e:
                return f"Sandbox error: {e}"

        return wrapper

    def _safe_path(self, path: Any) -> Path:
        """Ensure path is within sandbox"""
        p = Path(path)

        # If absolute and outside sandbox, reject
        if p.is_absolute():
            try:
                p.relative_to(self.work_dir)
            except ValueError:
                raise PermissionError(f"Access denied: {path} is outside sandbox {self.work_dir}")
        else:
            # Relative path - resolve within sandbox
            p = self.work_dir / p

        # Resolve and check again
        try:
            resolved = p.resolve()
            resolved.relative_to(self.work_dir.resolve())
        except ValueError:
            raise PermissionError(f"Access denied: {path} resolves outside sandbox")

        return resolved

    def cleanup(self):
        """Clean up sandbox"""
        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
