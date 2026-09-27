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
- **Description:** A severe loss (> $25,000) or suspicious claim being marked `auto_approved = True` without adjuster review.
- **Consequence:** Immediate financial leakage, fraudulent indemnity payouts, and reinsurance audit failures.
- **Mitigation Control (AC-03):** 
  Hard mathematical boundary enforced at both the node logic and Output Guardrail layer (`validate_triage_output`):
  ```python
  if estimated_damage > 25000.0 or fraud_risk_score >= 0.65 or is_quarantined:
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
