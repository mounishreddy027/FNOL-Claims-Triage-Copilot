"""
Consequential Action Audit Middleware
Business Case ID: BC-AAIE-HACK-06 (AC-10)

Appends machine-generated audit records:
{actor, action, tool, decision, timestamp}
for all consequential actions (coverage determinations, fraud flagging, routing, and guardrail blocks).
"""

import os
import re
import json
import datetime
from typing import Dict, Any, Optional
from src.memory.tiered_memory import mask_identifier

AUDIT_LOG_FILE = "logs/agent_actions.jsonl"

POLICY_PATTERN = r"\bPOL-(?!\*\*\*)[A-Z0-9]{4,10}-[A-Z0-9]{2}\b"
CLAIMANT_PATTERN = r"\bCLM-(?!\*\*\*)[A-Z0-9]{4,10}(?:-[A-Z0-9]+)?\b"
SSN_PATTERN = r"\b\d{3}-\d{2}-\d{4}\b"
CC_PATTERN = r"\b(?:\d{4}[- ]?){3}\d{4}\b"


def _sanitize_audit_obj(data: Any) -> Any:
    """Recursively sanitize identifiers, PII, and raw narratives from audit objects."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(raw_k in k.lower() for raw_k in ["raw_claim_text", "raw_text", "untrusted_text"]):
                sanitized[k] = "[REDACTED_RAW_NARRATIVE]"
            elif any(id_k in k.lower() for id_k in ["policy_number", "policy_id", "claimant_id", "ssn"]):
                sanitized[k] = mask_identifier(str(v))
            else:
                sanitized[k] = _sanitize_audit_obj(v)
        return sanitized
    elif isinstance(data, list):
        return [_sanitize_audit_obj(item) for item in data]
    elif isinstance(data, str):
        s = re.sub(POLICY_PATTERN, lambda m: mask_identifier(m.group(0)), data)
        s = re.sub(CLAIMANT_PATTERN, lambda m: mask_identifier(m.group(0)), s)
        s = re.sub(SSN_PATTERN, "[REDACTED_SSN]", s)
        s = re.sub(CC_PATTERN, "[REDACTED_CC]", s)
        return s
    return data


def log_agent_action(
    actor: str,
    action: str,
    tool: Optional[str],
    decision: Any,
    details: Optional[Dict[str, Any]] = None
):
    """Append a machine-generated consequential action to logs/agent_actions.jsonl with PII masking."""
    os.makedirs("logs", exist_ok=True)
    
    clean_decision = _sanitize_audit_obj(decision)
    clean_details = _sanitize_audit_obj(details or {})
    
    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "tool": tool,
        "decision": clean_decision,
        "details": clean_details
    }
    
    with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

