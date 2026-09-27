# Specification 07: Evaluation & Agent Testing
**Business Case ID:** BC-AAIE-HACK-06  
**System:** FNOL Claims-Triage Copilot  
**Test Framework:** Pytest (31 passing tests)  

## 1. Test Suite Coverage
1. `tests/test_context_engineering.py`: Verifies prompt injection neutralization, context compression, and pipeline integration.
2. `tests/test_guardrails.py`: Validates input PII redaction, threat blocking, AC-03 output gating, and auto-approval overrides.
3. `tests/test_mcp_server.py`: Tests MCP tools (`lookup_policy_details`, `calculate_claim_risk_score`), resource reads, and transcript logging.
4. `tests/test_memory_persistence.py`: Validates PII masking and cross-session semantic recall.
5. `tests/test_observability.py`: Tests Phoenix instrumentation, span recording, Parquet/JSONL export, and golden signals generation.
6. `tests/test_rag_tool.py`: Tests FAISS vector search across collision, comprehensive, and racing exclusion clauses.
7. `tests/test_routing.py`: Validates fast-track, high-value, fraud-suspected, and injection-quarantine routing end-to-end.\n