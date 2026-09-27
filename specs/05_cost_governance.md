# Specification 05: Cost & Resource Governance
**Business Case ID:** BC-AAIE-HACK-06  
**System:** FNOL Claims-Triage Copilot  

## 1. Cost Optimization Techniques
- **Context Summarization**: Pre-compressing claimant statements reduces LLM input tokens by 40-60%.
- **Targeted RAG Retrieval**: Embedding-filtered policy clause retrieval (top-k=3) avoids stuffing entire insurance policies into LLM prompts.
- **Local MCP Tool Execution**: Risk scoring and policy verification execute locally without invoking external cloud APIs.

## 2. Cost Accounting
All model interactions are tracked with token accounting in span attributes, allowing granular cost tracking per claim and per worker agent.\n