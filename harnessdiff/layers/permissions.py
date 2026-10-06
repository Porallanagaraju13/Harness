"""
Permission and Approval Layer

Chapters 20-22 of the handbook:
- Approval and containment solve different problems
- Keep credentials out of untrusted execution
- Observations have provenance
"""

import json
from pathlib import Path
from typing import Dict, Callable, Set, Optional
from harnessdiff.config import HarnessConfig


class PermissionLayer:
    """
    Enforces permission checks and approval for risky actions.
    
    Chapter 20: "Approval and containment solve different problems"
    Chapter 26: "Deterministic enforcement vs model judgment"
    """
    
    def __init__(self, config: HarnessConfig):
        self.config = config
        self.policy = self._load_policy()
        self.audit_log = []
    
    def _load_policy(self) -> Dict[str, any]:
        """Load permission policy"""
        if self.config.policy_file and self.config.policy_file.exists():
            with open(self.config.policy_file) as f:
                return json.load(f)
        
        # Default policy
        return {
            "dangerous_operations": [
                "delete_file",
                "shell",
                "exec",
                "remove",
                "drop_database"
            ],
            "dangerous_patterns": [
                "rm -rf",
                "del /f",
                "DROP TABLE",
                "DELETE FROM"
            ],
            "allowed_paths": [],
            "forbidden_paths": [
                "important_data",
                "critical",
                "production",
                ".git",
                "credentials"
            ]
        }
    
    def wrap_tools(self, tools: Dict[str, Callable]) -> Dict[str, Callable]:
        """Wrap tools with permission checks"""
        wrapped = {}
        
        for name, tool_fn in tools.items():
            wrapped[name] = self._make_checked(name, tool_fn)
        
        return wrapped
    
    def _make_checked(self, tool_name: str, tool_fn: Callable) -> Callable:
        """Add permission check to tool"""
        def wrapper(**kwargs):
            # Check if operation is dangerous
            if self._is_dangerous_operation(tool_name, kwargs):
                # Log attempt
                self.audit_log.append({
                    "tool": tool_name,
                    "args": kwargs,
                    "decision": "denied"
                })
                
                if self.config.auto_deny_dangerous:
                    # Provide guidance on safer alternative
                    if "delete" in tool_name.lower() or "rm" in str(kwargs).lower():
                        return (f"Permission denied: {tool_name} on sensitive path. "
                               f"Use list_files to see safe paths, or target only temp_* directories.")
                    return f"Permission denied: {tool_name} is a dangerous operation. Check policy."
                else:
                    # Simulate approval (in real system, would be async)
                    self.audit_log[-1]["decision"] = "approved_simulated"
            
            # Execute
            try:
                result = tool_fn(**kwargs)
                self.audit_log.append({
                    "tool": tool_name,
                    "args": kwargs,
                    "decision": "executed",
                    "result": str(result)[:100]
                })
                return result
            except Exception as e:
                self.audit_log.append({
                    "tool": tool_name,
                    "args": kwargs,
                    "decision": "error",
                    "error": str(e)
                })
                raise
        
        return wrapper
    
    def _is_dangerous_operation(self, tool_name: str, args: Dict) -> bool:
        """Check if operation is dangerous"""
        # Check tool name
        if tool_name in self.policy["dangerous_operations"]:
            return True
        
        # Check arguments for dangerous patterns
        args_str = json.dumps(args).lower()
        for pattern in self.policy["dangerous_patterns"]:
            if pattern.lower() in args_str:
                return True
        
        # Check paths
        for key in ["path", "file", "directory"]:
            if key in args:
                path_str = str(args[key])
                for forbidden in self.policy["forbidden_paths"]:
                    if forbidden in path_str:
                        return True
        
        return False
    
    def get_audit_log(self) -> list:
        """Get audit log of all permission checks"""
        return self.audit_log
