"""
Context Management Layer

Chapters 12-15 of the handbook:
- Active context is a harness decision
- Progressive disclosure instead of monolithic instructions
- Durable history and active context are different state surfaces
- Compaction is lossy
"""

from typing import List
from harnessdiff.config import HarnessConfig
from harnessdiff.models import Message


class ContextManagementLayer:
    """
    Manages context window to prevent overflow and maintain relevance.
    
    Chapter 12: "The harness determines what enters [context]"
    Chapter 15: "Compaction is lossy"
    """
    
    def __init__(self, config: HarnessConfig):
        self.config = config
    
    def select_context(self, messages: List[Message]) -> List[Message]:
        """
        Select relevant messages for next model call.
        
        Implements simple compaction when context gets too large.
        """
        # Estimate total tokens
        total_tokens = sum(
            self._estimate_message_tokens(msg) for msg in messages
        )
        
        if total_tokens <= self.config.max_context_tokens:
            return messages
        
        # Need to compact - keep system and user messages, compact middle
        system_msgs = [m for m in messages if m.role == "system"]
        user_msgs = [m for m in messages if m.role == "user"]
        other_msgs = [m for m in messages if m.role not in ["system", "user"]]
        
        # Keep recent messages
        recent_count = 10
        recent_msgs = other_msgs[-recent_count:] if len(other_msgs) > recent_count else other_msgs
        
        # Create summary of compacted messages
        if len(other_msgs) > recent_count:
            compacted_count = len(other_msgs) - recent_count
            summary = Message(
                role="system",
                content=f"[Context compacted: {compacted_count} earlier messages summarized. "
                       f"This is lossy as warned in Chapter 15 of the handbook.]"
            )
            return system_msgs + [summary] + user_msgs + recent_msgs
        
        return system_msgs + user_msgs + other_msgs
    
    def _estimate_message_tokens(self, msg: Message) -> int:
        """Rough token estimate for a message"""
        content_len = len(msg.content or "") // 4
        
        if msg.tool_calls:
            # Tool calls add tokens
            tool_len = len(str(msg.tool_calls)) // 4
            return content_len + tool_len
        
        return content_len
