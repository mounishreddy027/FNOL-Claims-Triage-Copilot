# FNOL Claims-Triage Copilot - Module Specifications

This folder contains the module specifications and documentation for the FNOL Claims-Triage Copilot hackathon implementation (Business Case: BC-AAIE-HACK-06).

## Specification Modules:
1. 01_agentic_core.md: LangGraph multi-agent architecture, typed state, supervisor, worker agents, checkpointing, and conditional routing.
2. 02_context_engineering.md: Context isolation, summarization, prompt injection quarantine, and memory tiers.
3. 03_mcp_server.md: Custom MCP stdio server specification (>=2 tools + 1 resource) and LangChain MCP adapters.
4. 04_observability.md: Arize Phoenix instrumentation, OpenInference tracing, span exports, and golden-signals calculation.
5. 05_cost_governance.md: Token and latency tracking, budget limits, cost dashboard generation.
6. 06_security_guardrails.md: PII masking (Presidio), input/output guardrails, audit logging.
7. 07_evaluation_testing.md: DeepEval LLM-as-judge benchmarks, golden test sets, agent unit tests.
