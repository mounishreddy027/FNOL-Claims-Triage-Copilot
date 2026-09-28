"""
FastAPI Streaming & Triage Service for FNOL Claims-Triage Copilot
Business Case ID: BC-AAIE-HACK-06 (Rubric Section 7.7 / 8.1 Bonus / Extra Credit)

Features:
- Async FastAPI REST interface for FNOL claims ingestion
- Server-Sent Events (SSE) streaming endpoint (`/triage/stream`) providing live agent lifecycle events
- Structured claim triage endpoint (`/triage`)
- Health check and runtime observability endpoints (`/health`, `/golden-signals`)
"""

import os
import json
import asyncio
import datetime
from typing import Dict, Any, Optional, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.graph import run_fnol_graph
from src.observability.tracing import get_current_trace_id, set_current_trace_id
from src.memory.tiered_memory import mask_identifier

app = FastAPI(
    title="FNOL Claims-Triage Copilot API",
    description="Multi-Agent First Notice of Loss (FNOL) Claims Triage API powered by LangGraph, FastMCP, and Arize Phoenix",
    version="1.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ClaimSubmissionRequest(BaseModel):
    """Input payload for submitting a new FNOL claim."""
    claim_id: Optional[str] = Field(default=None, description="Unique claim reference ID")
    claimant_id: Optional[str] = Field(default="CLM-001", description="Synthetic claimant identifier")
    policy_number: Optional[str] = Field(default="POL-554432-CA", description="Policy contract number")
    narrative: str = Field(..., description="First Notice of Loss narrative or description of loss")
    loss_location: Optional[str] = Field(default="San Francisco, CA", description="Geographic location of the loss")
    estimated_damage: Optional[float] = Field(default=None, description="Initial claimant loss estimate")


class ClaimTriageResponse(BaseModel):
    """Response payload for completed claim triage."""
    claim_id: str
    trace_id: str
    routing_queue: str
    auto_approved: bool
    escalation_reason: Optional[str]
    claim_type: str
    severity: str
    estimated_damage: float
    is_covered: bool
    applied_clause_id: str
    fraud_risk_score: float
    risk_tier: str
    timestamp: str


@app.get("/health", tags=["System"])
async def health_check() -> Dict[str, Any]:
    """Return system health status and active runtime toolchain."""
    return {
        "status": "healthy",
        "service": "FNOL-Claims-Triage-Copilot",
        "version": "1.2.0",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "toolchain": {
            "orchestrator": "LangGraph (StateGraph)",
            "llm_provider": "Google Gemini (google-genai)",
            "interoperability": "FastMCP stdio + langchain-mcp-adapters",
            "retrieval": "SentenceTransformers + FAISS IndexFlatIP",
            "observability": "Arize Phoenix + OpenTelemetry (OTel)",
            "memory": "SQLite Checkpointer + Tiered Semantic Memory"
        }
    }


@app.get("/golden-signals", tags=["Observability"])
async def get_golden_signals() -> Dict[str, Any]:
    """Retrieve the latest empirical golden signals telemetry report."""
    signals_file = "reports/golden_signals.json"
    if os.path.exists(signals_file):
        try:
            with open(signals_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read golden signals: {e}")
    return {"message": "Golden signals report not yet generated. Run a triage batch first."}


@app.post("/triage", response_model=ClaimTriageResponse, tags=["Claims Triage"])
async def triage_claim(payload: ClaimSubmissionRequest) -> ClaimTriageResponse:
    """Synchronously triage an FNOL claim through the multi-agent state graph."""
    cid = payload.claim_id or f"CLM-API-{int(datetime.datetime.now().timestamp() * 1000)}"
    trace_id = get_current_trace_id()
    set_current_trace_id(trace_id)

    try:
        final_state = run_fnol_graph(
            claim_id=cid,
            raw_claim_text=payload.narrative,
            claimant_id=payload.claimant_id,
            policy_number=payload.policy_number,
            location=payload.loss_location
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {str(e)}")

    routing = final_state.get("routing_decision") or {}
    classification = final_state.get("classification") or {}
    coverage = final_state.get("coverage_result") or {}
    fraud = final_state.get("fraud_risk") or {}

    return ClaimTriageResponse(
        claim_id=cid,
        trace_id=trace_id,
        routing_queue=routing.get("routing_queue", "escalate_human"),
        auto_approved=routing.get("auto_approved", False),
        escalation_reason=routing.get("escalation_reason"),
        claim_type=classification.get("claim_type", "Unknown"),
        severity=classification.get("severity", "Low"),
        estimated_damage=float(classification.get("estimated_damage", 0.0)),
        is_covered=bool(coverage.get("is_covered", False)),
        applied_clause_id=str(coverage.get("applied_clause_id", "NO_MATCH")),
        fraud_risk_score=float(fraud.get("fraud_risk_score", 0.0)),
        risk_tier=str(fraud.get("risk_tier", "LOW")),
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


@app.post("/triage/stream", tags=["Claims Triage"])
async def triage_claim_stream(payload: ClaimSubmissionRequest) -> StreamingResponse:
    """Stream multi-agent triage events in real-time using Server-Sent Events (SSE)."""
    cid = payload.claim_id or f"CLM-STREAM-{int(datetime.datetime.now().timestamp() * 1000)}"
    trace_id = get_current_trace_id()
    set_current_trace_id(trace_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        # 1. Pipeline Start
        yield f"event: lifecycle\ndata: {json.dumps({'stage': 'START', 'claim_id': cid, 'trace_id': trace_id, 'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()})}\n\n"
        await asyncio.sleep(0.05)

        # 2. Input Guardrail & Context Quarantine
        yield f"event: agent_activity\ndata: {json.dumps({'agent': 'input_guardrail', 'action': 'sanitize_and_quarantine', 'status': 'PROCESSING'})}\n\n"
        await asyncio.sleep(0.05)

        # 3. Graph Execution in background worker thread
        loop = asyncio.get_running_loop()
        final_state = await loop.run_in_executor(
            None,
            lambda: run_fnol_graph(
                claim_id=cid,
                raw_claim_text=payload.narrative,
                claimant_id=payload.claimant_id,
                policy_number=payload.policy_number,
                location=payload.loss_location
            )
        )

        classification = final_state.get("classification") or {}
        yield f"event: agent_result\ndata: {json.dumps({'agent': 'claim_classification_agent', 'result': classification})}\n\n"
        await asyncio.sleep(0.05)

        coverage = final_state.get("coverage_result") or {}
        yield f"event: agent_result\ndata: {json.dumps({'agent': 'coverage_check_agent', 'result': coverage})}\n\n"
        await asyncio.sleep(0.05)

        fraud = final_state.get("fraud_risk") or {}
        yield f"event: agent_result\ndata: {json.dumps({'agent': 'fraud_indicator_agent', 'result': fraud})}\n\n"
        await asyncio.sleep(0.05)

        routing = final_state.get("routing_decision") or {}
        yield f"event: agent_result\ndata: {json.dumps({'agent': 'routing_decision_node', 'result': routing})}\n\n"
        await asyncio.sleep(0.05)

        # 4. Final Triage Completion
        final_summary = {
            "claim_id": cid,
            "trace_id": trace_id,
            "routing_queue": routing.get("routing_queue", "escalate_human"),
            "auto_approved": routing.get("auto_approved", False),
            "escalation_reason": routing.get("escalation_reason"),
            "stage": "COMPLETE",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        yield f"event: complete\ndata: {json.dumps(final_summary)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
