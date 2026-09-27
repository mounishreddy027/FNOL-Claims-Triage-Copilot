# Specification 03: Model Context Protocol (MCP) Server
**Business Case ID:** BC-AAIE-HACK-06  
**System:** FNOL Claims-Triage Copilot  
**Protocol:** Model Context Protocol (MCP) via stdio transport  

## 1. Server Capabilities
The custom MCP server (`mcp_server/server.py`) provides:
- **Tools**:
  1. `lookup_policy_details`: Retrieves policy status, effective dates, vehicle details, deductibles, and limits.
  2. `calculate_claim_risk_score`: Evaluates actuarial risk metrics based on loss amount, inception tenure, and prior loss frequency.
- **Resources**:
  1. `policy://rules/standard_guidelines`: Serves authoritative underwriting and claims triage guidelines (FNOL-GUIDE-2026).

## 2. Adapter Integration
Integrated into the LangGraph agent graph via `langchain-mcp-adapters` and `LocalMCPClientAdapter`, offering stdio communication and local direct execution for maximum reliability.

## 3. Machine-Generated Transcripts
All tool calls and resource reads are automatically appended to `logs/mcp_transcript.jsonl` with latencies, masked parameters, and output results.\n