"""
Output Guardrails: PII Leakage Check and Auto-Approval Gating Enforcement
Business Case ID: BC-AAIE-HACK-06 (AC-03 / AC-06 / AC-10)
"""

import re
from typing import Dict, Any, List, Literal
from pydantic import BaseModel, Field
from src.guardrails.input_guardrails import SSN_PATTERN, CREDIT_CARD_PATTERN


class OutputGuardrailResult(BaseModel):
    """Structured result of output guardrail validation."""
    passed: bool
    action: Literal["ALLOW", "OVERRIDE", "BLOCK"]
    validated_output: Dict[str, Any]
    violations: List[str] = Field(default_factory=list)


def validate_triage_output(
    routing_decision: Dict[str, Any],
    fraud_risk: Dict[str, Any],
    classification: Dict[str, Any]
) -> OutputGuardrailResult:
    """Enforce safety and compliance constraints on final agent decisions before dispatch.
    
    AC-03 Gating Rule: Suspected-fraud or high-value claims MUST NOT be auto-approved.
    AC-06 Leakage Rule: Sensitive PII must not appear in output rationale.
    """
    violations = []
    output_copy = dict(routing_decision)
    action = "ALLOW"

    fraud_score = fraud_risk.get("fraud_risk_score", 0.0)
    requires_siu = fraud_risk.get("requires_siu_referral", False)
    estimated_damage = classification.get("estimated_damage", 0.0)
    severity = classification.get("severity", "Low")
    is_auto_approved = output_copy.get("auto_approved", False)

    # 1. AC-03 Gating Enforcement: Fraud claims must NEVER be auto-approved
    if (requires_siu or fraud_score >= 0.65) and is_auto_approved:
        violations.append("Violation AC-03: Fraud-suspected claim was erroneously auto-approved. Overriding to False.")
        output_copy["auto_approved"] = False
        output_copy["routing_queue"] = "investigate"
        output_copy["escalation_reason"] = "Guardrail Override: Mandatory SIU referral for suspected fraud."
        action = "OVERRIDE"

    # 2. AC-03 Gating Enforcement: High-value claims (>= $25k or severe) must NEVER be auto-approved
    if (estimated_damage >= 25000.0 or severity in ["High", "Severe"]) and is_auto_approved:
        violations.append("Violation AC-03: High-value claim was erroneously auto-approved. Overriding to False.")
        output_copy["auto_approved"] = False
        output_copy["routing_queue"] = "escalate_human"
        output_copy["escalation_reason"] = "Guardrail Override: Claims exceeding $25,000 threshold require human adjuster sign-off."
        action = "OVERRIDE"

    # 3. PII Leakage Check on output rationale
    rationale = output_copy.get("rationale", "")
    if re.search(SSN_PATTERN, rationale) or re.search(CREDIT_CARD_PATTERN, rationale):
        violations.append("Violation AC-06: Potential PII leakage detected in routing rationale.")
        output_copy["rationale"] = re.sub(SSN_PATTERN, "[REDACTED_SSN]", rationale)
        output_copy["rationale"] = re.sub(CREDIT_CARD_PATTERN, "[REDACTED_CC]", output_copy["rationale"])
        action = "OVERRIDE"

    return OutputGuardrailResult(
        passed=True,
        action=action,
        validated_output=output_copy,
        violations=violations
    )
