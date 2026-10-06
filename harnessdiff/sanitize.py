"""
Secret scrubbing for traces and results.

Ensures API keys, bearer tokens, and auth headers never land in published JSONL.
"""

from __future__ import annotations

import re
from typing import Any, Callable, List, Match, Tuple

# Env / field names that must never be serialized
_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "api-key",
        "authorization",
        "auth",
        "access_token",
        "access-token",
        "refresh_token",
        "x-api-key",
        "x_api_key",
        "gemini_api_key",
        "openai_api_key",
        "anthropic_api_key",
        "password",
        "secret",
        "token",
        "credential",
        "credentials",
    }
)

_REDACTED = "[REDACTED]"

# Patterns that look like secrets in free-form strings.
_SECRET_PATTERNS: List[Tuple[re.Pattern[str], Callable[[Match[str]], str]]] = [
    (re.compile(r"(?i)(authorization\s*[:=]\s*)(bearer\s+)?\S+"), lambda m: m.group(1) + _REDACTED),
    (re.compile(r"(?i)(x-api-key\s*[:=]\s*)\S+"), lambda m: m.group(1) + _REDACTED),
    (re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)\S+"), lambda m: m.group(1) + _REDACTED),
    (re.compile(r"(?i)\bsk-[A-Za-z0-9_\-]{8,}\b"), lambda m: _REDACTED),
    (re.compile(r"(?i)\bAIza[0-9A-Za-z_\-]{10,}\b"), lambda m: _REDACTED),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*\b"), lambda m: "Bearer " + _REDACTED),
    (
        re.compile(r"(?i)(GEMINI_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY)\s*=\s*\S+"),
        lambda m: m.group(1) + "=" + _REDACTED,
    ),
]


def _key_looks_secret(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    if normalized in _SECRET_KEYS:
        return True
    return any(
        part in normalized for part in ("api_key", "authorization", "secret", "token", "password")
    )


def scrub_string(value: str) -> str:
    """Redact secret-looking substrings from a string."""
    scrubbed = value
    for pattern, replacer in _SECRET_PATTERNS:
        scrubbed = pattern.sub(replacer, scrubbed)
    return scrubbed


def scrub_value(value: Any) -> Any:
    """Recursively scrub secrets from JSON-serializable values."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if isinstance(k, str) and _key_looks_secret(k):
                out[k] = _REDACTED
            else:
                out[k] = scrub_value(v)
        return out
    if isinstance(value, list):
        return [scrub_value(item) for item in value]
    if isinstance(value, tuple):
        return [scrub_value(item) for item in value]
    if isinstance(value, str):
        return scrub_string(value)
    return value


def scrub_jsonl_line(line: str) -> str:
    """Parse one JSONL line, scrub, and re-serialize."""
    import json

    line = line.strip()
    if not line:
        return line
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return scrub_string(line)
    return json.dumps(scrub_value(payload), ensure_ascii=False)
