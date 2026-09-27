"""
Context Engineering - Quarantine of Untrusted Claimant-Supplied Text
Business Case ID: BC-AAIE-HACK-06 (AC-06 / NFR-03)

Ensures untrusted free-text content is scanned, sanitized, and isolated so that
prompt injection payloads or adversarial directives are never treated as system instructions.
"""

import re
from typing import Tuple, Optional, List
from pydantic import BaseModel, Field
from src.memory.tiered_memory import mask_identifier


INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"system\s+prompt",
    r"override\s+(policy|rules|instructions)",
    r"exfiltrate",
    r"bypass\s+(verification|check|guardrail)",
    r"do\s+not\s+route\s+to\s+investigation",
    r"grant\s+admin",
    r"drop\s+table",
    r"sudo\s+",
    r"<script>",
    r"assistant\s*:\s*approve",
]


class QuarantinedClaimContent(BaseModel):
    """Structured container isolating untrusted user input."""
    original_text: str
    sanitized_text: str
    is_quarantined: bool
    detected_patterns: List[str] = Field(default_factory=list)
    quarantine_reason: Optional[str] = None


def quarantine_untrusted_input(raw_text: str) -> QuarantinedClaimContent:
    """Scan and quarantine untrusted claimant input."""
    detected = []
    sanitized = raw_text

    for pattern in INJECTION_PATTERNS:
        matches = re.findall(pattern, raw_text, re.IGNORECASE)
        if matches:
            detected.append(pattern)
            sanitized = re.sub(pattern, "[QUARANTINED_PROMPT_INJECTION]", sanitized, flags=re.IGNORECASE)

    if detected:
        return QuarantinedClaimContent(
            original_text=raw_text,
            sanitized_text=sanitized,
            is_quarantined=True,
            detected_patterns=detected,
            quarantine_reason="Adversarial prompt injection pattern detected in claimant text."
        )

    return QuarantinedClaimContent(
        original_text=raw_text,
        sanitized_text=raw_text,
        is_quarantined=False,
        detected_patterns=[],
        quarantine_reason=None
    )
