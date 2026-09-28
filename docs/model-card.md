# Model Card: FNOL Claims-Triage Copilot
**Model Version:** 1.0.0  
**Release Date:** September 2026  
**Business Case ID:** `BC-AAIE-HACK-06`  
**Base Foundation Model:** Google Gemini (Gemini 2.0 / 1.5 Flash via Google GenAI SDK)  
**Agentic Architecture:** LangGraph Hierarchical Multi-Agent Graph (Supervisor + 3 Specialized Workers)  

---

## 1. Model Overview & Purpose
The **FNOL Claims-Triage Copilot** is an enterprise AI multi-agent decision support system designed for property and casualty (P&C) auto insurance carriers. It automates First Notice of Loss (FNOL) intake by:
1. Classifying loss incident types and quantifying damage severity.
2. Cross-referencing loss descriptions against policy contracts using Agentic RAG.
3. Screening for early fraud signals and anomalous inception timing via FastMCP actuarial tools.
4. Triaging claims into 4 distinct queues: `fast-track`, `standard`, `investigate`, or `escalate_human`.

---

## 2. Intended Domain & Use Cases
- **Intended Uses:**
  - Automated intake and routing of first-party auto collision and comprehensive claims.
  - Identification of low-value, low-risk claims eligible for accelerated digital settlement ($< \$5,000$).
  - Detection and rapid escalation of high-severity losses ($> \$25,000$) to Senior Claims Adjusters.
  - Referral of high-risk claims ($\ge 0.65$ fraud score) to the Special Investigation Unit (SIU).
- **Out-of-Scope & Prohibited Uses:**
  - Autonomous claim denial or policy cancellation without licensed human adjuster sign-off.
  - Direct issuance of indemnity funds or digital payment settlement without policyholder verification.
  - Underwriting risk profiling or consumer credit evaluation.

---

## 3. Architecture & Data Flow

```
[Claim Narrative] -> [Input Guardrails: PII Redaction & Injection Quarantine]
                   -> [LangGraph Supervisor Coordinator]
                        ├── [Worker 1: Claim Classification Agent]
                        ├── [Worker 2: Coverage Check Agent (Policy RAG Tool)]
                        └── [Worker 3: Fraud Indicator Agent (FastMCP Server)]
                   -> [Routing Decision Node]
                   -> [Output Guardrail: AC-03 Gating Enforcement]
                   -> [Final Triage Queue Dispatch]
```

---

## 4. Training, Corpora & Grounding
- **Policy Corpus:** 5 synthetic policy contracts covering collision (`POL-SEC-04-COLLISION`), comprehensive perils (`POL-SEC-06-COMPREHENSIVE`), property damage (`POL-SEC-01-PROPERTY`), exclusions (`POL-EXCL-08-COMMERCIAL_RACING`), and fraud protocols (`POL-SIU-02-FRAUD_SCREENING`).
- **Retrieval Engine:** FAISS vector store indexing policy clauses with exact deductible, limit, and condition metadata.
- **Data Privacy:** Synthetic data exclusively. Deterministic regex-based Presidio-aligned PII masking scrubs SSNs, payment cards, and telephone numbers before reaching model context; policy and claimant IDs are masked.

---

## 5. Performance Bounds & Golden Signals
Empirical telemetry measured from actual test runs (see [`reports/golden_signals.json`](../reports/golden_signals.json) and [`reports/eval_report.json`](../reports/eval_report.json)):

| Performance Metric | Evaluation Target | Measured Benchmark Result | Supporting Verification Reference |
|:---|:---:|:---:|:---|
| **Routing Accuracy** | $\ge 90.0\%$ | **100.0%** | `tests/test_routing.py`, `src/cli.py` batch evaluation |
| **Hallucination Rate (Grounded)** | $\le 5.0\%$ | **0.0%** | `scripts/eval_deepeval.py` Cases 1–3 grounded evaluation |
| **Hallucination Recall (Negative)** | $\ge 90.0\%$ | **100.0%** | `scripts/eval_deepeval.py` Case 4 negative racing case caught |
| **Pipeline Success Rate** | $\ge 99.0\%$ | **100.0%** | `tests/test_remediation.py`, `run.py` end-to-end execution |
| **PII Redaction Recall** | $\ge 95.0\%$ | **100.0%** | `tests/test_guardrails.py`, `tests/test_remediation.py` |

---

## 6. Ethical Considerations & Safety Controls
- **AC-03 Contract Enforcement:** Hard-coded guardrail prevents automated approvals of claims $\ge \$25,000$ or fraud score $\ge 0.65$. Any attempt by the model to auto-approve high-value or fraud claims is intercepted and overridden to `False` in [`src/guardrails/output_guardrails.py`](../src/guardrails/output_guardrails.py).
- **Anti-Jailbreak Protection:** Input sanitization in [`src/guardrails/input_guardrails.py`](../src/guardrails/input_guardrails.py) isolates prompt injections (`ignore previous instructions`, `override policy`) into quarantined tokens, preventing model prompt hijacking.
- **Fairness Controls:** Claims triage decisions do not ingest protected characteristics (race, gender, age, religion, credit scores) and are grounded exclusively in physical loss damage, policy contract terms, and verified police report status.