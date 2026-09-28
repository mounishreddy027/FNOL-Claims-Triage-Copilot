# Output Risk Taxonomy & Consequential Safety Assurance

**Project:** FNOL Claims-Triage Copilot  
**Document Version:** 1.1.0  
**Business Case ID:** BC-AAIE-HACK-06  
**Regulatory Framework:** NAIC Model Unfair Claims Settlement Practices Act (#900), EU AI Act (High-Risk Categorization), GDPR Art. 22  

---

## 1. Consequential Risk Definition

Under insurance regulatory standards and AI safety frameworks, First Notice of Loss (FNOL) triage decisions are classified as **consequential algorithmic operations**. An error in claim routing directly impacts:
1. Legal entitlement to policy benefits.
2. Financial liability of the insurer and policyholder.
3. Consumer rights under statutory claim payment timeliness rules.
4. Referral of policyholders to criminal Special Investigation Units (SIU).

This document establishes the risk taxonomy, gating controls, and automated guardrails that prevent harmful, biased, or unauthorized outputs.

---

## 2. Consequential Risk Taxonomy

### Risk 1: Erroneous Auto-Approval of High-Value or Fraudulent Losses
- **Description:** A severe loss (> $25,000), suspicious claim, or compromised session being marked `auto_approved = True` without adjuster review.
- **Consequence:** Immediate financial leakage, fraudulent indemnity payouts, and reinsurance audit failures.
- **Mitigation Control (AC-03):** 
  Hard mathematical boundary enforced at both the node logic and Output Guardrail layer (`validate_triage_output`):
  ```python
  if estimated_damage > 25000.0 or fraud_risk_score >= 0.65 or is_quarantined or state.get("errors"):
      auto_approved = False  # Strictly mandatory override
  ```

### Risk 2: Wrongful Denial / Bad-Faith Claim Escalation
- **Description:** Denying coverage automatically based on unverified RAG citations without licensed human review.
- **Consequence:** Regulatory sanctions under NAIC #900, bad-faith litigation, and mandatory statutory interest penalties.
- **Mitigation Control (AC-03 & AC-04):**
  The AI system is strictly prohibited from executing final coverage denials. If `is_covered == False`, the claim is routed to `escalate_human` with mandatory clause citations (`POL-EXCL-...`). The human claims adjuster retains sole authority to issue formal declination letters.

### Risk 3: Downstream PII / Privacy Leakage
- **Description:** Claimant personal identifying information (Social Security Numbers, credit cards, telephone numbers, unmasked policy numbers) exposed in downstream logging, Phoenix spans, or third-party analytical pipelines.
- **Consequence:** Violation of GDPR, CCPA/CPRA, and state insurance department privacy regulations.
- **Mitigation Control (AC-06 & AC-10):**
  Bidirectional sanitization:
  - Input Guardrail sanitizes PII before state ingestion.
  - Span recorder and audit middleware (`_sanitize_audit_obj`) scrub all outputs, ensuring only masked IDs (`POL-***-CA`, `CLM-***-US`) reach disk or Phoenix telemetry.

### Risk 4: Actuarial Bias & Disparate Impact
- **Description:** Triage algorithms disproportionately routing claims based on proxy demographic attributes or geography rather than verified actuarial risk factors.
- **Consequence:** Discrimination litigation, civil rights violations, and state regulatory disapproval.
- **Mitigation Control:**
  Risk calculation is isolated in the deterministic MCP server (`calculate_claim_risk_score`), based strictly on transparent objective factors: damage amount, loss type, policyholder tenure, and prior loss frequency. Demographic attributes are excluded from graph state.

### Risk 5: Silent Tool / Memory Failure Inducing Blind Auto-Approval
- **Description:** MCP server timeout, tool invocation failure, or SQLite memory corruption silently failing without setting risk flags, resulting in default fast-track approval.
- **Consequence:** Substandard claims bypass security and actuarial screening undetected.
- **Mitigation Control:**
  Fail-closed defense: Any exception in MCP tool execution (`lookup_policy_details`, `calculate_claim_risk_score`) or memory recall/commit appends to `state["errors"]`. The `routing_decision_node` explicitly inspects `state["errors"]`; if any errors are present, `auto_approved` is unconditionally forced to `False` and routing is directed to `escalate_human`.
  Furthermore, physical violent threats (`action == "BLOCK"`) halt graph execution immediately before any worker agents run.

---

## 2.1 Consequential Output Tiers, Gating Controls & Concrete Samples

The system categorizes all prospective triage outputs into three distinct risk tiers:

### Tier 1: Low-Risk Output Tier (Automated Fast-Track Settlement)
- **Scope & Thresholds:** Estimated damage $\le \$5,000.00$, low severity, fraud risk score $< 0.25$, verified policy coverage clause, zero PII/injection violations, and zero system errors.
- **Gating Mechanism:** Auto-approval permitted (`auto_approved = True`). Dispatches to digital payout engine.
- **Concrete Sample Payload:**
  ```json
  {
    "claim_id": "CLM-2026-001",
    "routing_queue": "fast-track",
    "auto_approved": true,
    "claim_type": "Auto Collision",
    "severity": "Low",
    "estimated_damage": 1800.0,
    "applied_clause_id": "POL-SEC-04-COLLISION",
    "deductible": 500.0,
    "fraud_risk_score": 0.10,
    "risk_tier": "LOW",
    "escalation_reason": null,
    "rationale": "Low-severity, low-damage claim with clear coverage and low fraud risk approved for instant digital settlement."
  }
  ```

### Tier 2: Medium-Risk Output Tier (Standard Claims Adjuster Assignment)
- **Scope & Thresholds:** Estimated damage between $\$5,000.00$ and $\$24,999.00$, moderate severity, fraud risk between $0.25$ and $0.64$.
- **Gating Mechanism:** Human-in-the-loop review mandatory (`auto_approved = False`). Assigned to field claims adjuster.
- **Concrete Sample Payload:**
  ```json
  {
    "claim_id": "CLM-2026-002",
    "routing_queue": "standard",
    "auto_approved": false,
    "claim_type": "Auto Collision",
    "severity": "Medium",
    "estimated_damage": 7500.0,
    "applied_clause_id": "POL-SEC-04-COLLISION",
    "deductible": 500.0,
    "fraud_risk_score": 0.35,
    "risk_tier": "MEDIUM",
    "escalation_reason": "Standard adjuster queue for moderate damage claim processing.",
    "rationale": "Moderate claim meets coverage criteria and proceeds to standard adjuster assignment."
  }
  ```

### Tier 3: High-Risk Output Tier (Mandatory Human Escalation / SIU / Refusal)
- **Scope & Thresholds:** Any claim exceeding $\$25,000.00$, severe structural loss, fraud risk $\ge 0.65$, SIU indicators, quarantined prompt injection, violent threat, policy exclusion violation, out-of-scope inquiry, or system tool error.
- **Gating Mechanism:** Strict Gating Refusal (`auto_approved = False`). Hard-coded override in [`src/guardrails/output_guardrails.py`](../src/guardrails/output_guardrails.py) and routing logic intercepts and prevents any automated settlement, routing directly to `investigate` (SIU) or `escalate_human`.
- **Concrete Sample Payload (High-Value Loss):**
  ```json
  {
    "claim_id": "CLM-2026-003",
    "routing_queue": "escalate_human",
    "auto_approved": false,
    "claim_type": "Auto Collision",
    "severity": "Severe",
    "estimated_damage": 32000.0,
    "applied_clause_id": "POL-SEC-04-COLLISION",
    "deductible": 500.0,
    "fraud_risk_score": 0.45,
    "risk_tier": "MEDIUM",
    "escalation_reason": "High-value claim threshold exceeded ($32,000.00) or severe loss tier.",
    "rationale": "Claims exceeding $25,000 or severe damage are escalated to Senior Claims Adjuster."
  }
  ```
- **Concrete Sample Payload (Prompt Injection / Security Refusal):**
  ```json
  {
    "claim_id": "CLM-2026-004",
    "routing_queue": "escalate_human",
    "auto_approved": false,
    "claim_type": "Auto Collision",
    "severity": "Low",
    "estimated_damage": 3500.0,
    "applied_clause_id": "POL-SEC-06-COMPREHENSIVE",
    "deductible": 250.0,
    "fraud_risk_score": 0.60,
    "risk_tier": "MEDIUM",
    "escalation_reason": "Adversarial prompt injection / security tampering attempt detected; routed to human investigator.",
    "rationale": "Claim narrative contained quarantined injection payloads. Automated auto-approval prohibited; routed to Human Review."
  }
  ```

---

## 3. Defense-in-Depth Control Architecture

```
+-------------------------------------------------------------------------------+
|                             RAW CLAIMANT NARRATIVE                            |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
| 1. INPUT GUARDRAIL & QUARANTINE (AC-06 / AC-10)                              |
|    - PII Redaction (SSN, CC, Phone)                                           |
|    - Prompt Injection Neutralization -> [QUARANTINED_PROMPT_INJECTION]        |
+-------------------------------------------------------------------------------+
                                      |
                                      v [Sanitized Text Only]
+-------------------------------------------------------------------------------+
| 2. LANGGRAPH SUPERVISOR & MULTI-AGENT WORKERS                                 |
|    - Classification Agent (Damage magnitude, Severity)                        |
|    - Coverage Check Agent (Sentence-Transformers + FAISS Dense RAG)          |
|    - Fraud Indicator Agent (Stdio MCP Actuarial Risk Tool + Memory Recall)    |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
| 3. OUTPUT GUARDRAIL GATING (AC-03)                                            |
|    - Enforces damage > $25k => NEVER auto-approved                            |
|    - Enforces fraud_score >= 0.65 => Route to 'investigate'                   |
|    - Overrides unauthorized auto-approvals before finalization                 |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
| 4. SANITIZED AUDIT & TRACE EXPORT                                             |
|    - logs/agent_actions.jsonl (Zero plain PII)                                |
|    - traces/phoenix_spans.parquet & jsonl (Masked identifiers)               |
+-------------------------------------------------------------------------------+
```

---

## 4. Verification and Compliance Attestation

All output risk mitigations are validated by automated unit tests in `tests/test_guardrails.py`, `tests/test_routing.py`, and `tests/test_remediation.py`. Continuous regression checks run on every pipeline execution.
