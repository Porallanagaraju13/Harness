"""
Retry and Idempotency Layer

Chapters 29-31 of the handbook:
- Recovery requires control state and world state
- Idempotency matters for retries
- Concurrency creates consistency problems
"""

import hashlib
import json
import time
from typing import Callable, Dict, Set

from harnessdiff.config import HarnessConfig


class RetryLayer:
    """
    Handles retries with idempotency tracking.

    Chapter 31: "Idempotency matters for retries"
    Automatic retry is a tool-specific policy, not universal strategy.
    """

    def __init__(self, config: HarnessConfig):
        self.config = config
        self.idempotency_keys: Set[str] = set()
        self.retry_counts: Dict[str, int] = {}

    def wrap_tools(self, tools: Dict[str, Callable]) -> Dict[str, Callable]:
        """Wrap tools with retry logic"""
        wrapped = {}

        for name, tool_fn in tools.items():
            wrapped[name] = self._make_retriable(name, tool_fn)

        return wrapped

    def _make_retriable(self, tool_name: str, tool_fn: Callable) -> Callable:
        """Add retry logic to tool"""

        def wrapper(**kwargs):
            # Generate idempotency key
            idem_key = self._generate_idempotency_key(tool_name, kwargs)

            # Check if already executed
            if self._is_idempotent_operation(tool_name):
                if idem_key in self.idempotency_keys:
                    return (
                        f"Skipped: {tool_name} already executed with these parameters (idempotent)"
                    )

            # Try execution with retries
            last_error = None
            retry_count = 0

            while retry_count <= self.config.max_retries:
                try:
                    result = tool_fn(**kwargs)

                    # Record idempotency key on success
                    if self._is_idempotent_operation(tool_name):
                        self.idempotency_keys.add(idem_key)

                    # Add metadata about retries
                    if retry_count > 0:
                        result = f"{result}\n[Succeeded after {retry_count} retries]"

                    return result

                except Exception as e:
                    last_error = e
                    retry_count += 1

                    # Check if retriable
                    if not self._is_retriable_error(e):
                        # Don't retry non-retriable errors
                        break

                    if retry_count <= self.config.max_retries:
                        time.sleep(0.1 * retry_count)  # Exponential backoff

            # All retries exhausted
            self.retry_counts[tool_name] = self.retry_counts.get(tool_name, 0) + 1

            return f"Error after {retry_count} attempts: {last_error}"

        return wrapper

    def _generate_idempotency_key(self, tool_name: str, args: Dict) -> str:
        """Generate unique key for this operation"""
        # Sort args for consistent hashing
        canonical = json.dumps({"tool": tool_name, "args": args}, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def _is_idempotent_operation(self, tool_name: str) -> bool:
        """
        Check if operation is naturally idempotent.

        Operations like set_status, create_with_id are idempotent.
        Operations like charge_card, send_email are not.
        """
        idempotent_patterns = ["read", "get", "list", "search", "check", "verify"]
        non_idempotent_patterns = ["create", "send", "charge", "increment", "append"]

        tool_lower = tool_name.lower()

        # Check for non-idempotent patterns first
        for pattern in non_idempotent_patterns:
            if pattern in tool_lower:
                return False

        # Check for idempotent patterns
        for pattern in idempotent_patterns:
            if pattern in tool_lower:
                return True

        # Default: assume not idempotent for safety
        return False

    def _is_retriable_error(self, error: Exception) -> bool:
        """Check if error is worth retrying"""
        error_str = str(error).lower()

        # Retriable: timeout, network, temporary
        retriable_patterns = ["timeout", "network", "temporary", "unavailable", "busy"]
        for pattern in retriable_patterns:
            if pattern in error_str:
                return True

        # Not retriable: validation, not found, permission
        non_retriable_patterns = ["invalid", "not found", "permission", "forbidden"]
        for pattern in non_retriable_patterns:
            if pattern in error_str:
                return False

        # Default: retry unknown errors
        return True
