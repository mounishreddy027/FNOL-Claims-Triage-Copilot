# Specification 01: Agentic Core Architecture
**Business Case ID:** BC-AAIE-HACK-06  
**System:** FNOL Claims-Triage Copilot  
**Framework:** LangGraph (StateGraph, MIT License) + Google Gemini API

## 1. Architectural Overview
The FNOL Claims-Triage Copilot leverages a supervisor-directed hierarchical multi-agent state graph. The Supervisor agent dynamically coordinates specialized worker agents across three core domains:
1. **Claim Classification Agent**: Categorizes loss type, assigns severity tier, and estimates loss magnitude.
2. **Coverage Check Agent**: Verifies loss coverage against policy contracts, extracts clause citations, and determines applicable deductibles and coverage limits via an Agentic RAG tool.
3. **Fraud Indicator Agent**: Assesses actuarial fraud indicators, unverified claims patterns, and anomalous timing via custom MCP tools.
4. **Routing Decision Node**: Synthesizes worker outputs, applies safety gating contracts (AC-03: no auto-approval for fraud or high-value claims), and dispatches to appropriate queues (`fast-track`, `standard`, `investigate`, `escalate_human`).

## 2. Typed State Schema (`FNOLState`)
The state is managed across node transitions using a strictly typed TypedDict:
- `claim_id` (str): Unique business claim identifier.
- `claimant_id_masked` (str): Masked identifier format `CLM-***-US`.
- `policy_number_masked` (str): Masked policy identifier format `POL-***-US`.
- `raw_claim_text` (str): Raw claimant narrative.
- `quarantined_text` (Optional[str]): Preserved malicious or unverified text.
- `is_quarantined` (bool): Security flag isolating adversarial content.
- `incident_date` (str): Incident date.
- `loss_location` (str): Geographic loss location.
- `classification` (Optional[Dict]): Validated `ClaimClassificationResult`.
- `coverage_result` (Optional[Dict]): Validated `CoverageCheckResult`.
- `fraud_risk` (Optional[Dict]): Validated `FraudScreeningResult`.
- `routing_decision` (Optional[Dict]): Validated `RoutingDecisionResult`.
- `current_step` (str): Current workflow node execution marker.
- `next_agent` (Optional[str]): Routing target selected by supervisor.
- `audit_trail` (List[Dict]): Chronological execution log.
- `errors` (List[str]): Trapped validation and operational warnings.

## 3. Node Boundary Contracts
Structured outputs are enforced at all node boundaries using Pydantic V2 models:
- `ClaimClassificationResult`
- `CoverageCheckResult`
- `FraudScreeningResult`
- `RoutingDecisionResult`

## 4. Checkpointing & Resilience
Graph execution state is checkpointed at each step using `langgraph-checkpoint-sqlite` (`SqliteSaver`). This guarantees:
- Step-by-step state recovery across crashes.
- Cross-session replayability and timeline auditing.
- Thread isolation via `configurable.thread_id`.\n