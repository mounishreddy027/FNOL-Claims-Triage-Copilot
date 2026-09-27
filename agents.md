# Antigravity Implementation Guide: FNOL Claims-Triage Copilot

Below is the complete, step-by-step documentation and prompt sequence to build the FNOL Claims-Triage Copilot using Google Antigravity.

## 1. AGENTS.md Configuration
Create this file in your root directory. This serves as the system prompt for your Antigravity agent, enforcing the strict technology stack and rules required by the hackathon.


# Antigravity Agent Directives: FNOL Claims-Triage Copilot

## Core Identity & Constraints
You are an expert Agentic AI Engineer tasked with building a First Notice of Loss (FNOL) Claims-Triage Copilot.
- **Language:** Python 3.11+ strictly. 
- **Framework:** LangGraph (MIT).
- **LLM Provider:** Google Gemini API exclusively. Do not use Claude or other providers.
- **Infrastructure:** Use `pip` for all installations. Do NOT use Docker or external database services[cite: 1].

## Required Toolchain
- **Interoperability:** MCP Python SDK (stdio) with `langchain-mcp-adapters`[cite: 1].
- **Memory:** `langgraph-checkpoint-sqlite` and LangMem[cite: 1].
- **Retrieval:** Chroma or FAISS with local Sentence-Transformers[cite: 1].
- **Observability:** Arize Phoenix + OpenTelemetry (`openinference-instrumentation-langchain`)[cite: 1].
- **Evaluation:** DeepEval using LLM-as-judge (Gemini) and `pytest` for agent testing[cite: 1].
- **Security:** Guardrails-AI or LLM Guard, Presidio for PII, and `python-dotenv`[cite: 1].

## Execution Rules
- Generate all data synthetically and ensure policy numbers and claimant IDs are masked in logs[cite: 1].
- Produce machine-generated evidence logs via committed middleware[cite: 1].
- All code must run locally via a CLI interface[cite: 1].