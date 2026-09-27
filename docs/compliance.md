# Regulatory Compliance & Acceptance Criteria Mapping
**Business Case ID:** `BC-AAIE-HACK-06`  
**System:** FNOL Claims-Triage Copilot  
**Organization:** Hackathon Technical Compliance & Governance Office  

---

## 1. Hackathon Acceptance Criteria (AC) Traceability Matrix

| Requirement ID | Specification | Implementation Component | Verification Evidence | Compliance Status |
|:---:|:---|:---|:---|:---:|
| **AC-01** | Multi-Agent LangGraph Supervisor Architecture | `src/graph.py` (`StateGraph`, `supervisor_node`, 3 worker agents) | `tests/test_routing.py`, `tests/test_loops.py` | **100% COMPLIANT** |
| **AC-02** | Structured Node Boundaries & Contracts | `ClaimClassificationResult`, `CoverageCheckResult`, `FraudScreeningResult`, `RoutingDecisionResult` | `tests/test_tool_contracts.py` | **100% COMPLIANT** |
| **AC-03** | Safety Gating Contract (No auto-approval for fraud/high-value claims) | `src/guardrails/output_guardrails.py` (`validate_triage_output`), `src/graph.py` | `tests/test_guardrails.py`, `tests/test_routing.py` | **100% COMPLIANT** |
| **AC-04** | FastMCP Server Interoperability (>=2 tools + 1 resource) | `mcp_server/server.py` (`lookup_policy_details`, `calculate_claim_risk_score`, `policy://rules/standard_guidelines`) | `tests/test_mcp_server.py`, `logs/mcp_transcript.jsonl` | **100% COMPLIANT** |
| **AC-05** | Agentic RAG over Synthetic Policy Corpus | `src/tools/rag_tool.py` (FAISS vector store, 5 markdown policy contracts) | `tests/test_rag_tool.py`, `logs/tool_calls.jsonl` | **100% COMPLIANT** |
| **AC-06** | Untrusted Context Quarantine Middleware | `src/context/quarantine.py`, `src/context/manager.py` | `tests/test_context_engineering.py`, `tests/test_routing.py` | **100% COMPLIANT** |
| **AC-07** | In-Process Observability (Arize Phoenix + OpenInference) | `src/observability/tracing.py` (`LangChainInstrumentor`, `record_span`) | `tests/test_observability.py`, Phoenix UI | **100% COMPLIANT** |
| **AC-08** | Golden Signals Telemetry Tracking | `src/observability/tracing.py` (`calculate_golden_signals`) | `reports/golden_signals.json` | **100% COMPLIANT** |
| **AC-09** | Machine-Readable Trace Export (Parquet & JSONL) | `src/observability/tracing.py` (`export_spans`) | `traces/phoenix_spans.parquet`, `traces/phoenix_spans.jsonl` | **100% COMPLIANT** |
| **AC-10** | Consequential Action Audit Trail | `src/observability/audit.py` (`log_agent_action`) | `logs/agent_actions.jsonl` | **100% COMPLIANT** |

---

## 2. Non-Functional Requirements (NFR) Traceability

| NFR ID | Requirement Summary | Architectural Control | Verification Method |
|:---:|:---|:---|:---|
| **NFR-01** | Zero Plaintext PII in Logs | `src/memory/tiered_memory.py` regex identifier masking (`mask_identifier`) applied to all tool calls and logs | `tests/test_memory_persistence.py`, `tests/test_guardrails.py` |
| **NFR-02** | Execution Resilience & Checkpointing | `SqliteSaver` SQLite checkpointing at every graph state transition | `tests/test_routing.py::test_sqlite_checkpoint_state_retrieval` |
| **NFR-03** | Prompt Injection Hardening | Dual-layer defense: Regex quarantine filter in `src/context/` + input guardrail sanitizer in `src/guardrails/` | `tests/test_context_engineering.py`, `tests/test_guardrails.py` |

---

## 3. Insurance Regulatory & Standards Alignment

### A. NAIC Model Bulletin on Artificial Intelligence Systems in Insurance
- **Human Oversight & Gating:** All claims exceeding $25,000, claims with severe structural damage, or claims triggering fraud indicators ($\ge 0.65$ or SIU flags) are mandatorily routed to licensed human adjusters. The system strictly prohibits automated claim denial without human review.
- **Fairness & Prohibited Attributes:** No protected characteristics (race, gender, religion, marital status, credit tier, zip-code profiling) are processed. Triage decisions are strictly derived from physical vehicle damage, collision mechanics, policy contract citations, and verified actuarial loss parameters.
- **Explainability & Transparency:** Every routing decision outputs a detailed legal/contractual rationale citing exact section identifiers (e.g. `POL-SEC-04-COLLISION`, `POL-SEC-06-COMPREHENSIVE`) and verbatim policy terms.

### B. Gramm-Leach-Bliley Act (GLBA) & State Financial Privacy
- **Safeguards Rule Compliance:** Sensitive financial details, payment card numbers, and Social Security Numbers are redacted before entering agent context.
- **Data Minimization:** Policy numbers and claimant identifiers are masked into non-identifying tokens (`POL-***-CA`, `CLM-***-US`) across all persistent logs and telemetry spans.

### C. SOC 2 Type II Audit Logging (Security & Availability)
- **Immutable Consequential Action Trail:** Every consequential agent decision (coverage determination, fraud flag, triage routing, guardrail intervention) is recorded to `logs/agent_actions.jsonl` with `{actor, action, tool, decision, timestamp}`.\n