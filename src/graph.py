"""
FNOL Claims-Triage Copilot - LangGraph Multi-Agent Architecture
Business Case ID: BC-AAIE-HACK-06

Features:
- Typed State (FNOLState)
- Supervisor Node conditionally routing claims to 3 specialized worker agents:
  1. Claim Classification Agent (claim type, severity, loss estimate)
  2. Coverage Check Agent (policy verification, clause citations)
  3. Fraud Indicator Agent (fraud screening, risk indicators)
- Routing Decision Node (fast-track, standard, investigate, escalate_human)
  Suspected-fraud or high-value claims are escalated to a human, never auto-approved.
- Checkpointing integration via langgraph-checkpoint-sqlite (SqliteSaver)
- Structured outputs enforced at node boundaries via Pydantic
- Untrusted text quarantine to neutralize prompt injections
"""

import os
import re
import json
import sqlite3
import datetime
import time
from typing import Dict, Any, List, Optional, Literal, Tuple
from typing_extensions import TypedDict
from pydantic import BaseModel, Field, ValidationError

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from src.memory.tiered_memory import mask_identifier, SemanticTieredMemory
from src.context.manager import ContextManager
from src.tools.rag_tool import get_policy_rag_tool
from mcp_server.client import LocalMCPClientAdapter
from src.guardrails.input_guardrails import validate_claim_input
from src.guardrails.output_guardrails import validate_triage_output
from src.observability.audit import log_agent_action
from src.observability.tracing import record_span, setup_phoenix_tracing
from src.llm import invoke_gemini_with_fallback, is_gemini_configured



# ==============================================================================
# Structured Output Schemas (Pydantic Models)
# ==============================================================================

class ClaimClassificationResult(BaseModel):
    """Structured output for the Claim Classification Agent."""
    claim_type: str = Field(description="Classified claim type (Auto Collision, Comprehensive, Property, Bodily Injury, Theft, Liability)")
    severity: Literal["Low", "Medium", "High", "Severe"] = Field(description="Severity tier of the loss")
    estimated_damage: float = Field(ge=0.0, description="Estimated total loss amount in USD")
    loss_summary: str = Field(description="Concise factual description of the incident")
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence score")


class CoverageCheckResult(BaseModel):
    """Structured output for the Coverage Check Agent."""
    is_covered: bool = Field(description="Whether the claim incident is covered under the policy")
    coverage_type: str = Field(description="Category of coverage applied")
    applied_clause_id: str = Field(description="Identifier of cited policy clause (e.g., POL-SEC-04-COLLISION)")
    clause_citation: str = Field(description="Exact verbatim or excerpted text of cited policy rule")
    deductible: float = Field(ge=0.0, description="Policy deductible amount in USD")
    coverage_limit: float = Field(ge=0.0, description="Maximum coverage limit in USD")
    rationale: str = Field(description="Detailed legal/contractual reasoning for coverage decision")


class FraudScreeningResult(BaseModel):
    """Structured output for the Fraud Indicator Agent."""
    fraud_risk_score: float = Field(ge=0.0, le=1.0, description="Calculated fraud risk score from 0.0 (safe) to 1.0 (fraud)")
    risk_tier: Literal["LOW", "MEDIUM", "HIGH"] = Field(description="Categorical risk tier")
    triggered_indicators: List[str] = Field(default_factory=list, description="List of specific fraud flags triggered")
    requires_siu_referral: bool = Field(description="True if claim warrants Special Investigation Unit referral")
    rationale: str = Field(description="Explanation of fraud risk assessment")


class RoutingDecisionResult(BaseModel):
    """Structured output for the Final Routing Decision."""
    routing_queue: Literal["fast-track", "standard", "investigate", "escalate_human"] = Field(
        description="Target triage queue"
    )
    auto_approved: bool = Field(
        description="Whether claim is auto-approved without human review (strictly False for fraud/high-value)"
    )
    escalation_reason: Optional[str] = Field(default=None, description="Reason if claim is escalated to human adjuster")
    rationale: str = Field(description="Comprehensive rationale for routing decision")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class SupervisorDecision(BaseModel):
    """Structured output for Supervisor routing step."""
    next_agent: Literal["claim_classification", "coverage_check", "fraud_indicator", "routing_decision", "end"]
    reason: str


# ==============================================================================
# Typed Graph State
# ==============================================================================

class FNOLState(TypedDict, total=False):
    """Typed state for the FNOL Claims-Triage Copilot LangGraph workflow."""
    claim_id: str
    claimant_id_masked: str
    policy_number_masked: str
    raw_claim_text: str
    sanitized_text: str
    quarantined_text: Optional[str]
    is_quarantined: bool
    incident_date: Optional[str]
    loss_location: Optional[str]
    classification: Optional[Dict[str, Any]]
    coverage_result: Optional[Dict[str, Any]]
    fraud_risk: Optional[Dict[str, Any]]
    routing_decision: Optional[Dict[str, Any]]
    current_step: str
    next_agent: Optional[str]
    audit_trail: List[Dict[str, Any]]
    errors: List[str]
    claimant_profile: Optional[Dict[str, Any]]
    prior_claims_count: int
    recalled_memories: List[Dict[str, Any]]


# ==============================================================================
# Context Engineering & Quarantine Middleware
# ==============================================================================

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"system\s+prompt",
    r"override\s+(policy|rules|instructions)",
    r"exfiltrate",
    r"bypass\s+(verification|check|guardrail)",
    r"do\s+not\s+route\s+to\s+investigation",
    r"grant\s+admin",
    r"drop\s+table",
]

def quarantine_untrusted_input(text: str) -> Tuple[str, Optional[str], bool]:
    """Sanitize and quarantine untrusted claimant-supplied input.
    
    Detects adversarial injection attacks and isolates malicious content
    so worker agents never process injections as instructions.
    """
    for pattern in INJECTION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Quarantine the suspicious input
            sanitized = re.sub(pattern, "[QUARANTINED_PROMPT_INJECTION]", text, flags=re.IGNORECASE)
            return sanitized, text, True
    return text, None, False


# ==============================================================================
# Worker Agent Logic & Node Implementations
# ==============================================================================

def _resolve_claimant_id(state: FNOLState) -> str:
    """Resolve a specific claimant ID for cross-session memory tracking."""
    if state.get("claimant_id"):
        return state["claimant_id"]
    masked = state.get("claimant_id_masked", "")
    if masked and masked not in ("CLM-***-US", "CLM-DEFAULT", "CLM-***-M"):
        return masked
    return state.get("claim_id") or masked or "CLM-DEFAULT"


def supervisor_node(state: FNOLState) -> Dict[str, Any]:
    """Supervisor agent coordinating claim triage workflow.
    
    Evaluates state and determines the next specialized worker agent.
    Enforces structured output at node boundaries.
    """
    audit_events = list(state.get("audit_trail", []))
    errors = list(state.get("errors", []))
    
    # Run input guardrail & context engineering pipeline on initial entry
    is_quarantined = state.get("is_quarantined", False)
    quarantined_text = state.get("quarantined_text")
    raw_text = state.get("raw_claim_text", "")
    sanitized_text = state.get("sanitized_text", "")
    if raw_text and not sanitized_text:
        guard_in = validate_claim_input(raw_text)
        if guard_in.action == "BLOCK":
            errors.append("Claim blocked by Input Guardrail: violent threat or abusive coercion detected.")
            log_agent_action("input_guardrail", "block_threat", None, "BLOCKED", {"violations": guard_in.violations})
            threat_reason = "Security Threat Guardrail: " + "; ".join(guard_in.violations)
            audit_events.append({
                "actor": "input_guardrail",
                "action": "halt_processing_and_route_human",
                "decision": "ESCALATE_HUMAN",
                "reason": threat_reason,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            })
            routing_decision = {
                "claim_id": state.get("claim_id", "UNKNOWN"),
                "recommended_queue": "ESCALATE_HUMAN",
                "auto_approved": False,
                "approval_rationale": "Automated triage halted by Security Threat Guardrail: violent threat or coercive pattern detected.",
                "escalation_reason": threat_reason,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
            try:
                from src.observability.tracing import record_span
                record_span(
                    name="threat_guardrail_block",
                    span_type="AGENT",
                    inputs={"raw_claim_text": "[REDACTED_RAW_NARRATIVE]"},
                    outputs={"routing_queue": "ESCALATE_HUMAN", "action": "BLOCK"},
                    latency_ms=2.5,
                    status="BLOCKED"
                )
            except Exception:
                pass
            return {
                "sanitized_text": guard_in.sanitized_text,
                "is_quarantined": True,
                "quarantined_text": raw_text,
                "routing_decision": routing_decision,
                "next_agent": "end",
                "errors": errors,
                "audit_trail": audit_events
            }
        elif guard_in.redacted_pii_count > 0:
            log_agent_action("input_guardrail", "sanitize_pii", None, f"Redacted {guard_in.redacted_pii_count} PII elements")

        ctx_mgr = ContextManager()
        processed_ctx = ctx_mgr.process_claim_input(raw_text)
        has_injection = processed_ctx["is_quarantined"] or any("prompt injection" in v.lower() for v in guard_in.violations)
        if has_injection:
            is_quarantined = True
            quarantined_text = raw_text
            quarantine_reason = processed_ctx.get("quarantine_reason") or "Prompt injection detected by input guardrail"
            audit_events.append({
                "actor": "supervisor",
                "action": "quarantine_untrusted_input",
                "decision": "flagged_injection",
                "reason": quarantine_reason,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            })
            log_agent_action("supervisor", "quarantine_untrusted_input", None, "flagged_injection", {"reason": quarantine_reason})

        # Set sanitized, quarantined text (isolated from raw instructions and PII)
        sanitized_text = guard_in.sanitized_text

    # Cross-session memory recall for claimant
    claimant_id = _resolve_claimant_id(state)
    claimant_profile = state.get("claimant_profile")
    prior_claims_count = state.get("prior_claims_count")
    recalled_memories = list(state.get("recalled_memories", []))
    if claimant_profile is None:
        try:
            mem_engine = SemanticTieredMemory()
            claimant_profile = mem_engine.get_claimant_profile(claimant_id)
            prior_claims = claimant_profile.get("prior_claims", [])
            if prior_claims_count is None:
                prior_claims_count = len(prior_claims)
            recalled_memories = prior_claims
            if prior_claims_count > 0:
                audit_events.append({
                    "actor": "supervisor",
                    "action": "recall_cross_session_memory",
                    "decision": f"Recalled {prior_claims_count} prior claims from long-term memory",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                })
                log_agent_action(
                    "supervisor",
                    "recall_cross_session_memory",
                    "SemanticTieredMemory",
                    f"Recalled {prior_claims_count} prior claims for claimant {claimant_id}",
                    {"claimant": claimant_id, "count": prior_claims_count}
                )
        except Exception:
            claimant_profile = {"claimant_id_masked": mask_identifier(claimant_id), "prior_claims": []}
            if prior_claims_count is None:
                prior_claims_count = 0
            recalled_memories = []
    elif prior_claims_count is None:
        prior_claims_count = len(claimant_profile.get("prior_claims", []))


    # Sequential routing logic across worker agents
    if state.get("classification") is None:
        decision = SupervisorDecision(
            next_agent="claim_classification",
            reason="Claim classification pending: assessing claim type, severity, and loss magnitude."
        )
    elif state.get("coverage_result") is None:
        decision = SupervisorDecision(
            next_agent="coverage_check",
            reason="Coverage check pending: checking loss against policy terms and clause citations."
        )
    elif state.get("fraud_risk") is None:
        decision = SupervisorDecision(
            next_agent="fraud_indicator",
            reason="Fraud screening pending: checking fraud risk signals and prior claim anomalies."
        )
    elif state.get("routing_decision") is None:
        decision = SupervisorDecision(
            next_agent="routing_decision",
            reason="All worker evaluations complete: determining routing queue and escalation posture."
        )
    else:
        decision = SupervisorDecision(
            next_agent="end",
            reason="Triage lifecycle complete."
        )

    audit_events.append({
        "actor": "supervisor",
        "action": "route_to_worker",
        "decision": decision.next_agent,
        "reason": decision.reason,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    })

    return {
        "current_step": "supervisor",
        "next_agent": decision.next_agent,
        "sanitized_text": sanitized_text,
        "is_quarantined": is_quarantined,
        "quarantined_text": quarantined_text,
        "claimant_profile": claimant_profile,
        "prior_claims_count": prior_claims_count,
        "recalled_memories": recalled_memories,
        "audit_trail": audit_events,
        "errors": errors
    }


def claim_classification_agent_node(state: FNOLState) -> Dict[str, Any]:
    """Worker Agent 1: Classifies claim type, severity, and loss estimate.
    
    Produces structured ClaimClassificationResult validated at node boundary.
    Strictly consumes sanitized/quarantined text to prevent prompt injection execution.
    """
    t0 = time.perf_counter()
    narrative = state.get("sanitized_text") or state.get("quarantined_text") or ""
    text_lower = narrative.lower()
    audit_events = list(state.get("audit_trail", []))

    # 1. Attempt live Google Gemini LLM classification first if API key is active
    gemini_result = None
    if is_gemini_configured():
        prompt = (
            f"You are an insurance FNOL claims classifier. Analyze the following sanitized loss narrative:\n"
            f"'{narrative}'\n\n"
            f"Classify the claim_type ('Auto Collision', 'Comprehensive', 'Property', 'Bodily Injury', 'Theft', 'Liability'), "
            f"severity ('Low', 'Medium', 'High', 'Severe'), estimated_damage (positive float), loss_summary, and confidence score."
        )
        gemini_result = invoke_gemini_with_fallback(
            prompt=prompt,
            response_schema=ClaimClassificationResult,
            system_instruction="You are an expert FNOL Claims Classification AI. Always output valid JSON matching the schema."
        )

    if gemini_result:
        result = gemini_result
        print(f"  [Agent: ClaimClassification] Generated via Live Gemini: {result.claim_type} (Severity: {result.severity}, Loss: ${result.estimated_damage:,.2f})")
    else:
        # Fallback to deterministic offline rules if Gemini is unavailable or key is not working
        claim_type = "Auto Collision"
        severity = "Low"
        estimated_damage = 3500.0
        confidence = 0.92

        if "totaled" in text_lower or "severe" in text_lower or "hospital" in text_lower or "airbag" in text_lower:
            severity = "Severe"
            estimated_damage = 32000.0
            confidence = 0.95
        elif "major" in text_lower or "highway" in text_lower or "t-bone" in text_lower:
            severity = "High"
            estimated_damage = 18000.0
            confidence = 0.90
        elif "minor" in text_lower or "scratch" in text_lower or "fender" in text_lower:
            severity = "Low"
            estimated_damage = 1800.0
            confidence = 0.94
        elif "moderate" in text_lower or "dent" in text_lower or "bumper" in text_lower:
            severity = "Medium"
            estimated_damage = 7500.0
            confidence = 0.88

        if "theft" in text_lower or "stolen" in text_lower:
            claim_type = "Theft"
        elif "tree" in text_lower or "roof" in text_lower or "water" in text_lower:
            claim_type = "Property Damage"
        elif "injury" in text_lower or "neck" in text_lower or "paramedics" in text_lower:
            claim_type = "Bodily Injury"

        summary = f"Claim classified as {claim_type} with {severity} severity. Estimated loss: ${estimated_damage:,.2f}."
        
        result = ClaimClassificationResult(
            claim_type=claim_type,
            severity=severity,
            estimated_damage=estimated_damage,
            loss_summary=summary,
            confidence=confidence
        )
        print(f"  [Agent: ClaimClassification] Generated via Deterministic Fallback: {result.claim_type} (Severity: {result.severity}, Loss: ${result.estimated_damage:,.2f})")

    latency_ms = max(0.5, (time.perf_counter() - t0) * 1000.0)
    audit_events.append({
        "actor": "claim_classification_agent",
        "action": "classify_claim",
        "decision": result.model_dump(),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    })
    log_agent_action("claim_classification_agent", "classify_claim", None, result.model_dump())
    record_span("claim_classification", "AGENT", {"sanitized_input_chars": len(narrative)}, result.model_dump(), latency_ms)

    return {
        "current_step": "claim_classification",
        "classification": result.model_dump(),
        "audit_trail": audit_events
    }


def coverage_check_agent_node(state: FNOLState) -> Dict[str, Any]:
    """Worker Agent 2: Checks loss against policy terms using Agentic-RAG tool and cites coverage clauses.
    
    Produces structured CoverageCheckResult validated at node boundary.
    Strictly consumes sanitized/quarantined text to prevent prompt injection execution.
    """
    t0 = time.perf_counter()
    audit_events = list(state.get("audit_trail", []))
    classification = state.get("classification") or {}
    claim_type = classification.get("claim_type", "Auto Collision")
    narrative = state.get("sanitized_text") or state.get("quarantined_text") or ""

    # 1. MCP Tool: Lookup policy status and coverages
    policy_number = state.get("policy_number_masked", "POL-DEFAULT")
    policy_details = LocalMCPClientAdapter.get_policy_details(policy_number)

    # 2. Agentic-RAG Tool: Search policy corpus for applicable clause and citation
    rag_tool = get_policy_rag_tool()
    rag_result = rag_tool.search_policy_coverage(query=narrative, agent="coverage_check_agent")

    is_covered = rag_result.get("is_covered", True)
    clause_id = rag_result.get("primary_clause_id", "POL-SEC-04-COLLISION")
    citation = rag_result.get("clause_citation", "")
    deductible = rag_result.get("deductible", 500.0)
    limit = rag_result.get("limit", 50000.0)

    # 3. Attempt live Google Gemini LLM coverage analysis if active
    gemini_cov = None
    if is_gemini_configured() and is_covered:
        cov_prompt = (
            f"Sanitized Claim narrative: '{narrative}'\n"
            f"Retrieved Policy Clause: {clause_id}\n"
            f"Policy Text Citation: '{citation}'\n"
            f"Policy Deductible: ${deductible}, Limit: ${limit}\n\n"
            f"Confirm coverage determination (is_covered: bool), coverage_type ('{claim_type}'), "
            f"applied_clause_id ('{clause_id}'), clause_citation, deductible, coverage_limit, and legal contractual rationale."
        )
        gemini_cov = invoke_gemini_with_fallback(
            prompt=cov_prompt,
            response_schema=CoverageCheckResult,
            system_instruction="You are an expert Insurance Coverage Legal Examiner. Output valid JSON."
        )

    if gemini_cov:
        result = gemini_cov
        print(f"  [Agent: CoverageCheck] Generated via Live Gemini: Covered={result.is_covered}, Clause='{result.applied_clause_id}'")
    else:
        # Fallback to deterministic offline rules if Gemini is unavailable or not working
        if not is_covered:
            rationale = f"Incident violates policy exclusions under clause {clause_id}."
        else:
            rationale = f"Incident covered under {clause_id} (Deductible: ${deductible:,.2f}, Limit: ${limit:,.2f}) as verified in policy corpus."

        result = CoverageCheckResult(
            is_covered=is_covered,
            coverage_type=claim_type,
            applied_clause_id=clause_id,
            clause_citation=citation,
            deductible=deductible,
            coverage_limit=limit,
            rationale=rationale
        )
        print(f"  [Agent: CoverageCheck] Generated via Deterministic Policy RAG: Covered={result.is_covered}, Clause='{result.applied_clause_id}'")

    latency_ms = max(0.5, (time.perf_counter() - t0) * 1000.0)
    audit_events.append({
        "actor": "coverage_check_agent",
        "action": "verify_coverage",
        "decision": result.model_dump(),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    })
    log_agent_action("coverage_check_agent", "verify_coverage", "PolicyRAGTool", result.model_dump())
    record_span("coverage_check", "AGENT", {"policy": mask_identifier(policy_number)}, result.model_dump(), latency_ms)

    return {
        "current_step": "coverage_check",
        "coverage_result": result.model_dump(),
        "audit_trail": audit_events
    }


def fraud_indicator_agent_node(state: FNOLState) -> Dict[str, Any]:
    """Worker Agent 3: Screens for fraud indicators, risk signals, and anomalies.
    
    Produces structured FraudScreeningResult validated at node boundary.
    Strictly consumes sanitized/quarantined text and recalls cross-session claim history.
    """
    t0 = time.perf_counter()
    audit_events = list(state.get("audit_trail", []))
    narrative = state.get("sanitized_text") or state.get("quarantined_text") or ""
    text_lower = narrative.lower()
    is_quarantined = state.get("is_quarantined", False)
    classification = state.get("classification") or {}
    damage_amount = classification.get("estimated_damage", 2500.0)
    claim_type = classification.get("claim_type", "Auto Collision")
    prior_claims_count = state.get("prior_claims_count", 0)

    # 1. Invoke Custom MCP Risk Calculator Tool with cross-session prior claims
    tenure = 1 if "immediately after purchase" in text_lower else 24
    mcp_risk = LocalMCPClientAdapter.calculate_risk(
        damage_amount=damage_amount,
        incident_type=claim_type,
        tenure_months=tenure,
        prior_claims=prior_claims_count
    )

    risk_score = mcp_risk["claim_risk_score"]
    indicators = list(mcp_risk["contributing_factors"])

    # 2. Screening indicator rules
    if is_quarantined:
        risk_score += 0.50
        indicators.append("Adversarial Prompt Injection / Instruction Tampering Attempt")

    if "cash" in text_lower or "no police" in text_lower or "unwitnessed" in text_lower:
        risk_score += 0.30
        indicators.append("Absence of official police report / Cash transaction claimed")

    if "immediately after purchase" in text_lower or "day after policy" in text_lower or "just bought" in text_lower:
        if "Policyholder tenure under 3 months (early loss window)" not in indicators:
            indicators.append("Loss occurred within immediate inception window (< 72 hours)")

    if "staged" in text_lower or "discrepancy" in text_lower:
        risk_score += 0.35
        indicators.append("Inconsistent loss circumstances / Conflicting driver statements")

    if prior_claims_count >= 2:
        if not any("prior claim" in ind.lower() for ind in indicators):
            indicators.append(f"Multiple prior claims recorded ({prior_claims_count} prior losses in cross-session memory)")
    elif prior_claims_count == 1:
        if not any("prior claim" in ind.lower() for ind in indicators):
            indicators.append("Prior claim recorded in cross-session memory")

    risk_score = min(1.0, max(0.0, risk_score))
    
    if risk_score >= 0.65:
        tier = "HIGH"
        requires_siu = True
        rationale = f"High fraud risk detected ({risk_score:.2f}). Triggered flags: {', '.join(indicators)}."
    elif risk_score >= 0.30:
        tier = "MEDIUM"
        requires_siu = False
        rationale = f"Moderate risk detected ({risk_score:.2f}). Triggered flags: {', '.join(indicators)}."
    else:
        tier = "LOW"
        requires_siu = False
        rationale = f"Low fraud risk ({risk_score:.2f}). No critical anomalies detected."

    result = FraudScreeningResult(
        fraud_risk_score=round(risk_score, 2),
        risk_tier=tier,
        triggered_indicators=indicators,
        requires_siu_referral=requires_siu,
        rationale=rationale
    )

    latency_ms = max(0.5, (time.perf_counter() - t0) * 1000.0)
    audit_events.append({
        "actor": "fraud_indicator_agent",
        "action": "screen_fraud",
        "decision": result.model_dump(),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    })
    log_agent_action("fraud_indicator_agent", "screen_fraud", "calculate_claim_risk_score", result.model_dump())
    record_span("fraud_indicator", "AGENT", {"damage": damage_amount, "prior_claims": prior_claims_count}, result.model_dump(), latency_ms)

    return {
        "current_step": "fraud_indicator",
        "fraud_risk": result.model_dump(),
        "audit_trail": audit_events
    }


def routing_decision_node(state: FNOLState) -> Dict[str, Any]:
    """Final routing node: Synthesizes evaluations and routes claim.
    
    AC-03: Suspected-fraud or high-value claims are escalated to a human, not auto-approved.
    Produces structured RoutingDecisionResult validated at node boundary.
    Persists claim history into cross-session SemanticTieredMemory.
    """
    t0 = time.perf_counter()
    audit_events = list(state.get("audit_trail", []))
    classification = state.get("classification") or {}
    coverage = state.get("coverage_result") or {}
    fraud = state.get("fraud_risk") or {}

    estimated_damage = classification.get("estimated_damage", 0.0)
    severity = classification.get("severity", "Low")
    is_covered = coverage.get("is_covered", True)
    fraud_score = fraud.get("fraud_risk_score", 0.0)
    requires_siu = fraud.get("requires_siu_referral", False)

    # Decision Matrix adhering strictly to AC-03
    if requires_siu or fraud_score >= 0.65:
        queue = "investigate"
        auto_approved = False
        escalation_reason = f"Special Investigation Unit (SIU) referral triggered due to high fraud risk score ({fraud_score:.2f})."
        rationale = f"Claim flagged for fraud investigation. Indicators: {fraud.get('triggered_indicators', [])}."

    elif state.get("is_quarantined") or any("injection" in str(ind).lower() for ind in fraud.get("triggered_indicators", [])):
        queue = "escalate_human"
        auto_approved = False
        escalation_reason = "Adversarial prompt injection / security tampering attempt detected; routed to human investigator."
        rationale = "Claim narrative contained quarantined injection payloads. Automated auto-approval prohibited; routed to Human Review."

    elif not is_covered:
        queue = "escalate_human"
        auto_approved = False
        escalation_reason = f"Coverage denial under clause {coverage.get('applied_clause_id', 'UNKNOWN')} requires licensed human adjuster review."
        rationale = f"Claim denied based on policy terms: {coverage.get('rationale')}."

    elif estimated_damage >= 25000.0 or severity in ["High", "Severe"]:
        queue = "escalate_human"
        auto_approved = False
        escalation_reason = f"High-value claim threshold exceeded (${estimated_damage:,.2f}) or severe loss tier."
        rationale = f"Claims exceeding $25,000 or severe damage are escalated to Senior Claims Adjuster."

    elif estimated_damage <= 5000.0 and severity == "Low" and fraud_score < 0.25 and is_covered:
        queue = "fast-track"
        auto_approved = True
        escalation_reason = None
        rationale = "Low-severity, low-damage claim with clear coverage and low fraud risk approved for instant digital settlement."

    else:
        queue = "standard"
        auto_approved = False
        escalation_reason = "Standard adjuster queue for moderate damage claim processing."
        rationale = "Moderate claim meets coverage criteria and proceeds to standard adjuster assignment."

    result = RoutingDecisionResult(
        routing_queue=queue,
        auto_approved=auto_approved,
        escalation_reason=escalation_reason,
        rationale=rationale
    )

    # Output Guardrail: Enforce AC-03 Gating & AC-06 PII Leakage prevention
    guard_out = validate_triage_output(result.model_dump(), fraud, classification)
    if guard_out.action == "OVERRIDE":
        result = RoutingDecisionResult(**guard_out.validated_output)
        log_agent_action("output_guardrail", "override_decision", None, result.model_dump(), {"violations": guard_out.violations})

    # Cross-Session Memory Persistence: Store resulting claim fact into SQLite memory
    try:
        mem_engine = SemanticTieredMemory()
        cid = _resolve_claimant_id(state)
        sid = state.get("claim_id", "default")
        mem_engine.store_fact(
            claimant_id=cid,
            key=f"claim_{int(datetime.datetime.now().timestamp() * 1000)}",
            value=f"Claim: {classification.get('claim_type', 'Auto')} - Loss: ${estimated_damage:,.2f} - Queue: {result.routing_queue}",
            category="claim_history",
            session_id=sid,
            metadata={
                "queue": result.routing_queue,
                "damage": estimated_damage,
                "risk_score": fraud_score,
                "clause_id": coverage.get("applied_clause_id", "")
            }
        )
    except Exception:
        pass

    latency_ms = max(0.5, (time.perf_counter() - t0) * 1000.0)
    audit_events.append({
        "actor": "routing_decision",
        "action": "finalize_routing",
        "decision": result.model_dump(),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    })
    log_agent_action("routing_decision", "finalize_routing", None, result.model_dump())
    record_span("routing_decision", "AGENT", {"queue": result.routing_queue}, result.model_dump(), latency_ms)

    return {
        "current_step": "routing_decision",
        "routing_decision": result.model_dump(),
        "audit_trail": audit_events
    }


# ==============================================================================
# Conditional Edge Router
# ==============================================================================

def route_next_worker(state: FNOLState) -> str:
    """Conditional edge router reading supervisor's next_agent decision."""
    next_agent = state.get("next_agent", "end")
    if next_agent == "claim_classification":
        return "claim_classification"
    elif next_agent == "coverage_check":
        return "coverage_check"
    elif next_agent == "fraud_indicator":
        return "fraud_indicator"
    elif next_agent == "routing_decision":
        return "routing_decision"
    return END


# ==============================================================================
# Graph Construction & Compilation
# ==============================================================================

def build_fnol_graph() -> StateGraph:
    """Construct the LangGraph StateGraph with supervisor and worker nodes."""
    workflow = StateGraph(FNOLState)

    # Register nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("claim_classification", claim_classification_agent_node)
    workflow.add_node("coverage_check", coverage_check_agent_node)
    workflow.add_node("fraud_indicator", fraud_indicator_agent_node)
    workflow.add_node("routing_decision", routing_decision_node)

    # Define edges: START enters supervisor
    workflow.add_edge(START, "supervisor")

    # Supervisor conditionally dispatches to workers or END
    workflow.add_conditional_edges(
        "supervisor",
        route_next_worker,
        {
            "claim_classification": "claim_classification",
            "coverage_check": "coverage_check",
            "fraud_indicator": "fraud_indicator",
            "routing_decision": "routing_decision",
            END: END
        }
    )

    # All worker nodes return control back to supervisor
    workflow.add_edge("claim_classification", "supervisor")
    workflow.add_edge("coverage_check", "supervisor")
    workflow.add_edge("fraud_indicator", "supervisor")
    workflow.add_edge("routing_decision", "supervisor")

    return workflow


def get_compiled_app(db_path: str = "data/checkpoints.sqlite"):
    """Compile the LangGraph graph with SqliteSaver checkpointer."""
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()
    
    graph = build_fnol_graph()
    app = graph.compile(checkpointer=checkpointer)
    return app, checkpointer


if __name__ == "__main__":
    print("Initializing FNOL Claims-Triage Copilot LangGraph...")
    app, checkpointer = get_compiled_app()
    
    sample_state: FNOLState = {
        "claim_id": "CLM-TEST-001",
        "claimant_id_masked": "CLM-***-AUTO",
        "policy_number_masked": "POL-***-US",
        "raw_claim_text": "Minor fender scratch while parking at grocery store. No injuries.",
        "quarantined_text": None,
        "is_quarantined": False,
        "incident_date": "2026-09-26",
        "loss_location": "Chicago, IL",
        "classification": None,
        "coverage_result": None,
        "fraud_risk": None,
        "routing_decision": None,
        "current_step": "init",
        "next_agent": None,
        "audit_trail": [],
        "errors": []
    }
    
    config = {"configurable": {"thread_id": "thread-demo-001"}}
    final_output = app.invoke(sample_state, config=config)
    print("\n--- Final Triage Result ---")
    print(f"Claim ID: {final_output['claim_id']}")
    print(f"Classification: {final_output['classification']}")
    print(f"Coverage: {final_output['coverage_result']}")
    print(f"Fraud Risk: {final_output['fraud_risk']}")
    print(f"Routing Decision: {final_output['routing_decision']}")
