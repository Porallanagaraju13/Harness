"""
Verification Layer

Chapters 25-28 of the handbook:
- Verification is different from self-reported completion
- Deterministic enforcement vs model judgment
- Generator and evaluator are different roles
- Feedback loops give the agent external evidence
"""

from typing import Callable, Optional
from harnessdiff.config import HarnessConfig


class VerificationLayer:
    """
    Independent verification of task completion.
    
    Chapter 25: "Verification is different from self-reported completion"
    "Whenever practical, completion should be tied to observable state 
    outside the model's own assertion."
    """
    
    def __init__(self, config: HarnessConfig):
        self.config = config
        self.verifier: Optional[Callable] = None
    
    def set_verifier(self, verifier_fn: Callable):
        """Set the verification function for current task"""
        self.verifier = verifier_fn
    
    def verify_completion(self, claim: str, context: dict) -> dict:
        """
        Verify if task is actually complete.
        
        Returns dict with:
        - verified: bool
        - evidence: str
        - agent_claim: str
        """
        if not self.verifier:
            return {
                "verified": False,
                "evidence": "No verifier configured",
                "agent_claim": claim,
                "note": "Cannot verify without verifier function"
            }
        
        try:
            # Run independent verification
            verification_result = self.verifier(context)
            
            return {
                "verified": verification_result.get("success", False),
                "evidence": verification_result.get("evidence", ""),
                "agent_claim": claim,
                "details": verification_result
            }
        
        except Exception as e:
            return {
                "verified": False,
                "evidence": f"Verification error: {e}",
                "agent_claim": claim
            }
