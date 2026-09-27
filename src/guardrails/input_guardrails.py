"""
Input Guardrails: PII Redaction, Toxic Content Detection, and Adversarial Injection Blocking
Business Case ID: BC-AAIE-HACK-06 (AC-06 / AC-10 / NFR-01 / NFR-03)
"""

import re
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from src.memory.tiered_memory import mask_identifier

# Regex patterns for sensitive PII
SSN_PATTERN = r"\b\d{3}-\d{2}-\d{4}\b"
CREDIT_CARD_PATTERN = r"\b(?:\d{4}[- ]?){3}\d{4}\b"
PHONE_PATTERN = r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b"
POLICY_UNMASKED_PATTERN = r"\bPOL-(?!\*\*\*)[A-Z0-9]{4,10}-[A-Z0-9]{2}\b"

# Adversarial prompt injection patterns
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

# Toxic / threat keywords
THREAT_PATTERNS = [
    r"\bkill\s+(you|the\s+adjuster|everyone)\b",
    r"\bbomb\s+(the\s+office|building)\b",
    r"\bi\s+will\s+destroy\b",
    r"\bpay\s+me\s+or\s+else\b"
]


class InputGuardrailResult(BaseModel):
    """Structured result of input guardrail validation."""
    passed: bool
    sanitized_text: str
    action: Literal["ALLOW", "SANITIZE", "BLOCK"]
    violations: List[str] = Field(default_factory=list)
    redacted_pii_count: int = 0


def validate_claim_input(text: str) -> InputGuardrailResult:
    """Validate and sanitize claimant input text against PII, injections, and threats."""
    violations = []
    sanitized = text
    pii_count = 0

    # 1. Threat / Violent abuse check (Blocks immediately)
    for pattern in THREAT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            violations.append("Violent threat or abusive coercion detected.")
            return InputGuardrailResult(
                passed=False,
                sanitized_text="[CONTENT_BLOCKED_DUE_TO_THREAT]",
                action="BLOCK",
                violations=violations,
                redacted_pii_count=0
            )

    # 2. Adversarial Injection Check (Blocks execution as instructions)
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            violations.append(f"Adversarial prompt injection pattern detected: {pattern}")
            sanitized = re.sub(pattern, "[QUARANTINED_PROMPT_INJECTION]", sanitized, flags=re.IGNORECASE)

    # 3. PII Redaction / Masking (Sanitizes)
    # Mask SSN
    ssn_matches = re.findall(SSN_PATTERN, sanitized)
    if ssn_matches:
        pii_count += len(ssn_matches)
        violations.append(f"Redacted {len(ssn_matches)} Social Security Number(s)")
        sanitized = re.sub(SSN_PATTERN, "[REDACTED_SSN]", sanitized)

    # Mask Credit Cards
    cc_matches = re.findall(CREDIT_CARD_PATTERN, sanitized)
    if cc_matches:
        pii_count += len(cc_matches)
        violations.append(f"Redacted {len(cc_matches)} Credit Card Number(s)")
        sanitized = re.sub(CREDIT_CARD_PATTERN, "[REDACTED_CC]", sanitized)

    # Mask Unmasked Policy Numbers
    pol_matches = re.findall(POLICY_UNMASKED_PATTERN, sanitized)
    for pol in pol_matches:
        pii_count += 1
        masked = mask_identifier(pol)
        sanitized = sanitized.replace(pol, masked)
        violations.append(f"Masked raw policy number {pol} -> {masked}")

    # Determine action
    if any("prompt injection" in v for v in violations):
        action = "SANITIZE"
        passed = True  # Safe to process sanitized text through quarantine pipeline
    elif pii_count > 0:
        action = "SANITIZE"
        passed = True
    else:
        action = "ALLOW"
        passed = True

    return InputGuardrailResult(
        passed=passed,
        sanitized_text=sanitized,
        action=action,
        violations=violations,
        redacted_pii_count=pii_count
    )
