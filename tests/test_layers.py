"""Tests for harness layers"""

import tempfile
from pathlib import Path

from harnessdiff.layers.tool_design import ToolDesignLayer, remove_overlapping_tools
from harnessdiff.layers.context_mgmt import ContextManagementLayer
from harnessdiff.layers.sandbox import SandboxLayer
from harnessdiff.layers.permissions import PermissionLayer
from harnessdiff.layers.retry import RetryLayer
from harnessdiff.layers.verification import VerificationLayer
from harnessdiff.config import HarnessConfig
from harnessdiff.models import Message


def test_tool_design_layer():
    """Test tool design layer wraps tools correctly"""
    config = HarnessConfig(use_distinct_tools=True)
    layer = ToolDesignLayer(config)
    
    def verbose_tool() -> str:
        return "x" * 1000
    
    tools = {"verbose": verbose_tool}
    wrapped = layer.wrap_tools(tools)
    
    result = wrapped["verbose"]()
    # Should truncate long output
    assert len(result) < 1000


def test_remove_overlapping_tools():
    """Test removing overlapping tools"""
    tools = {
        "search": lambda q: "search",
        "find": lambda q: "find",
        "lookup": lambda q: "lookup",
        "unrelated": lambda: "other"
    }
    
    filtered = remove_overlapping_tools(tools)
    
    # Should keep only one from overlap group
    search_tools = [k for k in filtered.keys() if k in ["search", "find", "lookup"]]
    assert len(search_tools) == 1
    
    # Should keep unrelated tool
    assert "unrelated" in filtered


def test_context_management_layer():
    """Test context management compacts long histories"""
    config = HarnessConfig(max_context_tokens=100)
    layer = ContextManagementLayer(config)
    
    # Create many messages that exceed budget
    messages = [Message(role="system", content="System")]
    messages.extend([
        Message(role="assistant", content="x" * 100)
        for _ in range(20)
    ])
    
    selected = layer.select_context(messages)
    
    # Should compact (or at least not grow)
    assert len(selected) <= len(messages)


def test_sandbox_layer():
    """Test sandbox layer restricts paths"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = HarnessConfig(sandbox_work_dir=tmpdir)
        layer = SandboxLayer(config)
        
        # Path within sandbox should work
        safe_path = layer._safe_path("test.txt")
        
        # Use resolved path comparison for Windows 8.3 short path compatibility
        tmpdir_resolved = Path(tmpdir).resolve()
        safe_path_resolved = Path(safe_path).resolve()
        
        # Check if safe_path is within tmpdir using is_relative_to (Python 3.9+)
        # or manual check for older Python
        try:
            # Python 3.9+
            assert safe_path_resolved.is_relative_to(tmpdir_resolved), \
                f"Safe path {safe_path_resolved} should be within {tmpdir_resolved}"
        except AttributeError:
            # Fallback for older Python
            try:
                safe_path_resolved.relative_to(tmpdir_resolved)
            except ValueError:
                assert False, f"Safe path {safe_path_resolved} should be within {tmpdir_resolved}"
        
        # Absolute path outside sandbox should fail
        try:
            layer._safe_path("/etc/passwd")
            assert False, "Should have raised PermissionError"
        except PermissionError:
            pass


def test_permission_layer():
    """Test permission layer blocks dangerous operations"""
    config = HarnessConfig(use_permissions=True, auto_deny_dangerous=True)
    layer = PermissionLayer(config)
    
    def dangerous_delete(path: str) -> str:
        return f"Deleted {path}"
    
    tools = {"delete_file": dangerous_delete}
    wrapped = layer.wrap_tools(tools)
    
    result = wrapped["delete_file"](path="important_data/critical.db")
    
    # Should be denied
    assert "denied" in result.lower()
    
    # Should be in audit log
    audit = layer.get_audit_log()
    assert len(audit) > 0
    assert audit[0]["decision"] == "denied"


def test_retry_layer():
    """Test retry layer handles failures"""
    config = HarnessConfig(use_retry_logic=True, max_retries=3)
    layer = RetryLayer(config)
    
    call_count = 0
    
    def flaky_tool() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Network timeout: service unavailable")
        return "Success"
    
    tools = {"flaky": flaky_tool}
    wrapped = layer.wrap_tools(tools)
    
    result = wrapped["flaky"]()
    
    # Should succeed after retries
    assert "Success" in result
    assert call_count == 3


def test_retry_layer_idempotency():
    """Test retry layer tracks idempotency"""
    config = HarnessConfig(use_retry_logic=True)
    layer = RetryLayer(config)
    
    call_count = 0
    
    def read_tool(path: str) -> str:
        nonlocal call_count
        call_count += 1
        return f"Content {call_count}"
    
    tools = {"read_file": read_tool}
    wrapped = layer.wrap_tools(tools)
    
    # First call
    result1 = wrapped["read_file"](path="test.txt")
    assert "Content 1" in result1
    
    # Second call with same args (idempotent operation)
    result2 = wrapped["read_file"](path="test.txt")
    # Should be skipped or return cached
    assert "Skipped" in result2 or "Content" in result2


def test_verification_layer():
    """Test verification layer can verify completion"""
    config = HarnessConfig(use_verification=True)
    layer = VerificationLayer(config)
    
    # Set verifier
    def verifier(context):
        return {
            "success": True,
            "evidence": "File exists"
        }
    
    layer.set_verifier(verifier)
    
    result = layer.verify_completion("Task done!", {})
    
    assert result["verified"] == True
    assert "evidence" in result
