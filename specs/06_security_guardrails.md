# Specification 06: Security, Guardrails & Compliance
**Business Case ID:** BC-AAIE-HACK-06  
**System:** FNOL Claims-Triage Copilot  

## 1. Input Guardrails (`src/guardrails/input_guardrails.py`)
- **PII Redaction**: Automatically detects and redacts SSNs (`[REDACTED_SSN]`), credit cards (`[REDACTED_CC]`), and masks policy identifiers (`POL-***-XX`).
- **Prompt Injection Defense**: Neutralizes adversarial instruction sequences.
- **Threat Detection**: Abusive coercion or violent threats are immediately blocked (`action="BLOCK"`).

## 2. Output Guardrails (`src/guardrails/output_guardrails.py`)
- **AC-03 Contract Enforcement**: Claims flagged for suspected fraud (risk >= 0.65 or SIU referral) or high value (estimated damage >= $25,000 or severe damage) are strictly prevented from auto-approval. Any illegal auto-approval is overridden to `False` and routed to human review.
- **PII Leakage Prevention**: Inspects final rationale and routing decisions to ensure no unmasked PII is leaked.

## 3. Consequential Action Audit Trail (`logs/agent_actions.jsonl`)
Every consequential decision (coverage determination, fraud flag, routing dispatch, guardrail override) is machine-logged with `{actor, action, tool, decision, timestamp}`.\n