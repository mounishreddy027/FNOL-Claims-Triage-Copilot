"""
Context Manager coordinating Write, Select, Compress, and Isolate operations.
"""

from typing import Dict, Any, Optional
from src.context.quarantine import quarantine_untrusted_input, QuarantinedClaimContent
from src.context.summarizer import ClaimSummarizer


class ContextManager:
    """Coordinates context engineering lifecycle for FNOL claims."""

    def __init__(self):
        self.summarizer = ClaimSummarizer()

    def process_claim_input(self, raw_claim_text: str) -> Dict[str, Any]:
        """Full context engineering pipeline: isolate -> compress -> select -> write."""
        # 1. Isolate: Quarantine untrusted text
        quarantine_result = quarantine_untrusted_input(raw_claim_text)
        
        # 2. Compress: Summarize the safe/sanitized content
        summary_result = self.summarizer.compress_narrative(quarantine_result.sanitized_text)

        # 3. Select & Write: Return optimized context package for worker agents
        return {
            "safe_text": quarantine_result.sanitized_text,
            "is_quarantined": quarantine_result.is_quarantined,
            "quarantined_text": quarantine_result.original_text if quarantine_result.is_quarantined else None,
            "quarantine_reason": quarantine_result.quarantine_reason,
            "condensed_summary": summary_result["condensed_summary"],
            "damage_level": summary_result["damage_level"],
            "police_involved": summary_result["police_involved"]
        }
