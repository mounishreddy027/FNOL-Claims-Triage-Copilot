# Complete Hackathon Rubric Checklist & Evidence Traceability Matrix

**Project:** FNOL Claims-Triage Copilot  
**Business Case ID:** `BC-AAIE-HACK-06`  
**Target Score:** 85+ / 100  
**Status:** FULLY RECONCILED & MACHINE-VERIFIED  

---

## 1. 100-Mark Rubric Category Mapping

| Category # | Rubric Category (Score Weight) | Core Requirements | Implementing Module | Automated Verification Test | Committed Evidence Artifact |
|:---:|:---|:---|:---|:---|:---|
| **CAT-01** | **Agentic Core & LangGraph (20 marks)** | Hierarchical supervisor pattern, ≥3 specialized workers, typed state, conditional edges, SQLite checkpointing | [`src/graph.py`](../src/graph.py) | `tests/test_routing.py`, `tests/test_loops.py` | `data/checkpoints.sqlite` |
| **CAT-02** | **MCP Toolchain & Interoperability (15 marks)** | FastMCP stdio server (≥2 tools + 1 resource) consumed via `langchain-mcp-adapters` with fallback | [`mcp_server/server.py`](../mcp_server/server.py), [`mcp_server/client.py`](../mcp_server/client.py) | `tests/test_mcp_server.py`, `tests/test_tool_contracts.py` | `logs/mcp_transcript.jsonl`, `logs/mcp_errors.jsonl` |
| **CAT-03** | **Context Engineering & Memory (15 marks)** | Adversarial quarantine filter, context compression, SQLite tiered memory + LangMem toolchain, cross-session recall | [`src/context/manager.py`](../src/context/manager.py), [`src/memory/tiered_memory.py`](../src/memory/tiered_memory.py) | `tests/test_context_engineering.py`, `tests/test_memory_persistence.py` | `data/semantic_memory.sqlite`, `logs/memory_test.log` |
| **CAT-04** | **Observability & Phoenix Tracing (15 marks)** | Arize Phoenix tracer, OpenTelemetry SDK integration, genuine 32-hex trace / 16-hex span IDs, Parquet/JSONL span export | [`src/observability/tracing.py`](../src/observability/tracing.py) | `tests/test_observability.py`, `tests/test_remediation.py` | `traces/phoenix_spans.parquet`, `traces/phoenix_spans.jsonl` |
| **CAT-05** | **Cost & Latency Governance (10 marks)** | Golden signals extraction (thinking/acting/tool p50/p95), non-double-counted tool latency, CSV & PNG dashboard | [`src/observability/tracing.py`](../src/observability/tracing.py), [`scripts/generate_dashboard_image.py`](../scripts/generate_dashboard_image.py) | `tests/test_observability.py` | `reports/golden_signals.json`, `reports/dashboard_data.csv`, `reports/dashboard.png` |
| **CAT-06** | **Security, Safety & Guardrails (10 marks)** | Input PII masking (Presidio-aligned regex), threat blocking, AC-03 output gating, consequential audit trail | [`src/guardrails/input_guardrails.py`](../src/guardrails/input_guardrails.py), [`src/guardrails/output_guardrails.py`](../src/guardrails/output_guardrails.py) | `tests/test_guardrails.py`, `tests/test_remediation.py` | `logs/agent_actions.jsonl` |
| **CAT-07** | **Evaluation & Governance Pack (15 marks)** | DeepEval LLM-as-judge benchmark over 9-case golden set, failure RCA citing real spans, risk register, model card | [`scripts/eval_deepeval.py`](../scripts/eval_deepeval.py), [`docs/`](../docs/) | `tests/test_evaluation_deepeval.py` | `reports/eval_report.json`, `reports/deepeval_benchmark.json`, `docs/failure-analysis.md` |

---

## 2. Acceptance Criteria (AC-01 through AC-12) Verification

| Criterion ID | Requirement Summary | Implementation & Control | Verification Test Suite | Committed Evidence |
|:---:|:---|:---|:---|:---|
| **AC-01** | Classify claim type/severity and cite policy coverage clause | `claim_classification_agent_node`, `coverage_check_agent_node`, `PolicyRAGTool` | `tests/test_routing.py`, `tests/test_rag_tool.py` | `logs/tool_calls.jsonl`, `traces/phoenix_spans.jsonl` |
| **AC-02** | Screen claim for fraud indicators and return fraud-risk signal | `fraud_indicator_agent_node`, `calculate_claim_risk_score` MCP tool | `tests/test_routing.py`, `tests/test_mcp_server.py` | `logs/mcp_transcript.jsonl` |
| **AC-03** | Route claims (fast-track/standard/investigate); fraud/high-value escalated to human | `routing_decision_node`, `validate_triage_output` ($>\$25k$, fraud $\ge 0.65$ -> escalate) | `tests/test_guardrails.py`, `tests/test_routing.py` | `logs/agent_actions.jsonl` |
| **AC-04** | Identify claim intent; escalate ambiguous or out-of-scope requests | `ClaimClassificationResult.intent`, routing checks for `OUT_OF_SCOPE` & `AMBIGUOUS` | `tests/test_remediation.py` | `reports/eval_report.json` (Case 5) |
| **AC-05** | Maintain context and recall prior-session facts on return visit | `SemanticTieredMemory`, `LangMem` integration, supervisor recall | `tests/test_memory_persistence.py` | `data/semantic_memory.sqlite`, `logs/memory_test.log` |
| **AC-06** | Handle untrusted claimant input safely; quarantine injections and mask PII | `validate_claim_input`, `quarantine_untrusted_input`, Presidio-aligned regex | `tests/test_context_engineering.py`, `tests/test_guardrails.py` | `logs/agent_actions.jsonl` (zero plaintext PII) |
| **AC-07** | Machine-generated tool invocation log reconciling with code | `logs/tool_calls.jsonl` written by tool decorator with exact metadata | `tests/test_tool_contracts.py` | `logs/tool_calls.jsonl` |
| **AC-08** | Failure analysis documenting $\ge 3$ real failures with run/span IDs | `docs/failure-analysis.md` citing verified committed trace IDs and error logs | `tests/test_remediation.py` | `docs/failure-analysis.md` |
| **AC-09** | Phoenix-derived golden signals report and visual cost/latency dashboard | `calculate_golden_signals`, `generate_dashboard_image` | `tests/test_observability.py` | `reports/golden_signals.json`, `reports/dashboard.png`, `reports/dashboard_data.csv` |
| **AC-10** | Input/output guardrails wired into agent I/O path with audit trail | Input and output validators in graph loop; `log_agent_action` | `tests/test_guardrails.py` | `logs/agent_actions.jsonl` |
| **AC-11** | Comprehensive governance pack with committed control citations | Risk register, model card, compliance mapping (EU AI Act, NIST AI RMF, DPDP), output risk | Manual & automated citation audit | `docs/risk-register.md`, `docs/model-card.md`, `docs/compliance.md`, `docs/output-risk.md` |
| **AC-12** | DeepEval LLM-as-judge benchmark report over balanced golden set | `scripts/eval_deepeval.py` testing 9 scenarios across all dimensions | `tests/test_evaluation_deepeval.py` | `reports/eval_report.json`, `reports/deepeval_benchmark.json` |

---

## 3. Non-Functional Requirements (NFR-01 through NFR-06)

| NFR ID | Requirement | Architectural Enforcement | Evidence Artifact |
|:---:|:---|:---|:---|
| **NFR-01** | Zero plaintext secrets committed; env-var config with `.env.example` | `.gitignore` covers `.env`; only `.env.example` committed; zero API keys committed | [`.gitignore`](../.gitignore), [`.env.example`](../.env.example) |
| **NFR-02** | Single command runs workflow; second regenerates traces and evaluation | `python run.py` executes full 4-phase lifecycle; single commands documented in README | [`run.py`](../run.py), [`README.md`](../README.md) |
| **NFR-03** | Untrusted claimant input is quarantined and never treated as instructions | Regex isolation in `src/context/quarantine.py` tags payloads `[QUARANTINED_PROMPT_INJECTION]` | [`src/context/quarantine.py`](../src/context/quarantine.py) |
| **NFR-04** | Async tool execution and graceful fallback on model/tool errors | `StdioMCPClientAdapter.ainvoke_tool`, Gemini 429 quota fallback, fail-closed routing | [`mcp_server/client.py`](../mcp_server/client.py), [`src/llm.py`](../src/llm.py) |
| **NFR-05** | All data synthetic; policy numbers and claimant IDs masked in logs | Deterministic `mask_identifier` applied before logging (`POL-***-CA`, `CLM-***-US`) | [`src/memory/tiered_memory.py`](../src/memory/tiered_memory.py), [`logs/`](../logs/) |
| **NFR-06** | Evidence artifacts machine-generated by committed code | Parquet, JSONL, JSON, CSV, and PNG outputs generated exclusively by runbook scripts | [`traces/`](../traces/), [`reports/`](../reports/), [`logs/`](../logs/) |

---

## 4. Required Artifacts Checklist (Rubric Section 7)

- [x] **`src/graph.py`**: StateGraph with typed state, supervisor, 3 worker nodes, SQLite checkpointer.
- [x] **`mcp_server/` + `logs/mcp_transcript.jsonl`**: Stdio FastMCP server with 2 tools + 1 resource consumed via `langchain-mcp-adapters`.
- [x] **`src/context/`**: Context manager with quarantine, compression, and PII sanitization.
- [x] **`src/memory/` + `tests/test_memory_persistence.py` + `logs/memory_test.log`**: Short + long-term memory with committed output log.
- [x] **`src/tools/rag_tool.py` + `data/policy_corpus/`**: Dense FAISS IndexFlatIP + SentenceTransformers RAG over synthetic policy contracts.
- [x] **`src/observability/tracing.py`**: OpenTelemetry SDK + Arize Phoenix integration.
- [x] **`traces/phoenix_spans.parquet` & `traces/phoenix_spans.jsonl`**: Measured execution spans with SDK-generated 32-hex trace IDs and 16-hex span IDs.
- [x] **`logs/tool_calls.jsonl`**: Machine-generated tool invocation logs with status, latency, args, result.
- [x] **`docs/failure-analysis.md`**: 3 real observed failures citing verifiable trace/log records.
- [x] **`reports/golden_signals.json`**: Empirical P50/P95 latencies, token counts, cost estimate, accuracy, hallucination.
- [x] **`reports/dashboard.png` + `reports/dashboard_data.csv`**: Visual dashboard and underlying CSV data file.
- [x] **`src/guardrails/`**: Input and output guardrails enforcing AC-03 gating and PII sanitization.
- [x] **`logs/agent_actions.jsonl`**: Consequential action audit log with actor, action, tool, decision, timestamp.
- [x] **`docs/risk-register.md`**: Risk register with OWASP/NIST categorizations, mitigations, and residual risk.
- [x] **`docs/model-card.md`**: Model card with Gemini foundation details, limitations, and performance bounds.
- [x] **`docs/compliance.md`**: NAIC, GLBA, EU AI Act, NIST AI RMF, and DPDP obligation mappings.
- [x] **`docs/output-risk.md`**: Low, medium, and high output risk classifications with gating controls and samples.
- [x] **`reports/eval_report.json`**: DeepEval benchmark report over balanced 9-case golden set.
- [x] **`tests/test_routing.py`**: Routing logic and worker state transition assertions.
- [x] **`tests/test_loops.py`**: Loop/cascade guard asserting recursion limit protection.
- [x] **`tests/test_tool_contracts.py`**: Input/output schema contracts and error path assertions.
- [x] **`src/api/` (Bonus)**: Async FastAPI streaming endpoint (`/triage/stream`) implementing SSE lifecycle events.
- [x] **`README.md`**: Complete runbook, commands, architecture diagrams, and verified test counts.
