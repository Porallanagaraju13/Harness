"""
Tool Design Layer

Chapters 5-10 of the handbook:
- Agent-Computer Interface (ACI)
- Tools are part of model input
- More tools can make decisions harder
- Tool results should return high-signal context
- Tool errors are observations too
"""

from typing import Dict, Callable, List, Any
from harnessdiff.config import HarnessConfig


class ToolDesignLayer:
    """
    Improves tool design to reduce selection difficulty and observation noise.
    
    Chapter 8: "More tools can make the decision harder"
    Chapter 9: "Tool results should return high-signal context"
    """
    
    def __init__(self, config: HarnessConfig):
        self.config = config
    
    def wrap_tools(self, tools: Dict[str, Callable]) -> Dict[str, Callable]:
        """
        Wrap tools to improve their output quality.
        
        Returns high-signal, concise results instead of verbose dumps.
        """
        wrapped = {}
        
        for name, tool_fn in tools.items():
            wrapped[name] = self._make_high_signal_wrapper(tool_fn)
        
        return wrapped
    
    def _make_high_signal_wrapper(self, tool_fn: Callable) -> Callable:
        """Wrap tool to return concise, structured results"""
        def wrapper(**kwargs):
            result = tool_fn(**kwargs)
            
            # If result is very long, truncate with explanation
            result_str = str(result)
            if len(result_str) > 500:
                truncated = result_str[:500]
                return f"{truncated}\n... (truncated, {len(result_str)} total chars)"
            
            return result
        
        return wrapper
    
    def improve_schemas(self, schemas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Improve tool schemas with clear descriptions.
        
        Chapter 7: "Tools are part of the model input"
        Tool names and descriptions affect inference before tools are called.
        """
        improved = []
        
        for schema in schemas:
            # Make descriptions more distinct and clear
            improved_schema = schema.copy()
            
            if "function" in improved_schema:
                func = improved_schema["function"]
                
                # Enhance description to be more specific
                if "description" in func:
                    desc = func["description"]
                    
                    # Add usage guidance
                    if "search" in func["name"].lower():
                        func["description"] = f"{desc} Use this to search for content."
                    elif "read" in func["name"].lower():
                        func["description"] = f"{desc} Use this to read existing files."
                    elif "write" in func["name"].lower():
                        func["description"] = f"{desc} Use this to create or modify files."
            
            improved.append(improved_schema)
        
        return improved


def remove_overlapping_tools(tools: Dict[str, Callable]) -> Dict[str, Callable]:
    """
    Remove overlapping tools to reduce selection difficulty.
    
    Chapter 8: If you have search(), find(), lookup(), query(), grep(), retrieve()
    all doing similar things, keep only the most appropriate one.
    """
    # Groups of overlapping tool names
    overlap_groups = [
        ["search", "find", "lookup", "query", "grep", "retrieve"],
        ["read", "get", "fetch", "load"],
        ["write", "create", "put", "save"],
    ]
    
    kept_tools = {}
    removed = set()
    
    for group in overlap_groups:
        # Find tools in this group
        group_tools = {}
        for name, fn in tools.items():
            name_lower = name.lower()
            for keyword in group:
                if keyword in name_lower and name not in removed:
                    group_tools[name] = fn
                    break
        
        if group_tools:
            # Keep the first one alphabetically (arbitrary but deterministic)
            chosen = sorted(group_tools.keys())[0]
            kept_tools[chosen] = group_tools[chosen]
            removed.update(k for k in group_tools.keys() if k != chosen)
    
    # Add tools that weren't in any overlap group
    for name, fn in tools.items():
        if name not in removed and name not in kept_tools:
            kept_tools[name] = fn
    
    return kept_tools
