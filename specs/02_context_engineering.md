# Specification 02: Context Engineering & Tiered Memory
**Business Case ID:** BC-AAIE-HACK-06  
**System:** FNOL Claims-Triage Copilot  

## 1. Context Isolation (Quarantine Middleware)
Claimant narratives are untrusted inputs subject to adversarial manipulation (e.g. indirect prompt injections, instruction overrides).
The quarantine pipeline (`src/context/quarantine.py`) performs:
1. **Adversarial Pattern Matching**: Detects patterns such as `ignore previous instructions`, `override policy`, `grant admin`, etc.
2. **Instruction Neutralization**: Replaces hostile command sequences with safe quarantine tokens (`[QUARANTINED_PROMPT_INJECTION]`).
3. **Isolation Storage**: Preserves raw inputs in an isolated quarantine tier while routing sanitized representations to worker agents.

## 2. Context Compression (`ClaimSummarizer`)
Long or repetitive claimant narratives are compressed into structured loss facts (vehicle speed, impact point, police involvement, drivability) to minimize LLM token bloat and maintain a compact context window.

## 3. Tiered Memory Architecture (`SemanticTieredMemory`)
The system implements a two-tier memory architecture:
1. **Short-Term Thread Memory**: Managed by `langgraph-checkpoint-sqlite`, retaining step transitions and scratchpads for active claim threads.
2. **Long-Term Semantic Memory**: Implemented via SQLite-backed persistent key-value store (`data/semantic_memory.sqlite`), enabling cross-session recall of customer claim history, policy status, and past dispute context.\n