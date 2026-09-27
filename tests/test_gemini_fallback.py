"""
Unit Tests for Google Gemini Live Invocation & Deterministic Offline Fallback
Business Case ID: BC-AAIE-HACK-06

Verifies:
1. When GEMINI_API_KEY is absent or placeholder, is_gemini_configured() is False.
2. When live Gemini API call fails (network, quota, invalid key), invoke_gemini_with_fallback() returns None safely.
3. LangGraph agent nodes seamlessly fall back to deterministic offline rules without crashing.
"""

import os
import pytest
from src.llm import is_gemini_configured, invoke_gemini_with_fallback
from src.graph import get_compiled_app, FNOLState, ClaimClassificationResult


def test_gemini_unconfigured_fallback(monkeypatch):
    """Verify is_gemini_configured correctly identifies placeholder or empty keys."""
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    assert is_gemini_configured() is False
    assert invoke_gemini_with_fallback("test prompt") is None

    monkeypatch.setenv("GEMINI_API_KEY", "your_gemini_api_key_here")
    monkeypatch.setenv("GOOGLE_API_KEY", "your_api_key_here")
    assert is_gemini_configured() is False
    assert invoke_gemini_with_fallback("test prompt") is None


def test_gemini_invalid_key_graceful_fallback(monkeypatch):
    """Verify invalid or failing Gemini API key does not crash and falls back safely."""
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy_INVALID_KEY_TEST_TRIGGER")
    assert is_gemini_configured() is True
    
    # Must catch exception internally and return None, triggering deterministic fallback
    result = invoke_gemini_with_fallback(
        prompt="Classify this claim",
        response_schema=ClaimClassificationResult
    )
    assert result is None  # Gracefully fell back!


def test_graph_resilience_under_gemini_failure(monkeypatch):
    """Verify the entire LangGraph pipeline completes successfully when Gemini fails."""
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy_SIMULATED_FAILING_KEY")
    app, checkpointer = get_compiled_app(db_path=":memory:")
    
    state: FNOLState = {
        "claim_id": "CLM-FALLBACK-001",
        "claimant_id_masked": "CLM-***-US",
        "policy_number_masked": "POL-***-US",
        "raw_claim_text": "Minor collision with grocery store bollard, bumper dented.",
        "quarantined_text": None,
        "is_quarantined": False,
        "incident_date": "2026-09-26",
        "loss_location": "Houston, TX",
        "classification": None,
        "coverage_result": None,
        "fraud_risk": None,
        "routing_decision": None,
        "current_step": "init",
        "next_agent": None,
        "audit_trail": [],
        "errors": []
    }
    
    config = {"configurable": {"thread_id": "thread-fallback-001"}}
    output = app.invoke(state, config=config)
    
    # Pipeline must succeed despite Gemini failure
    assert output["classification"] is not None
    assert output["coverage_result"] is not None
    assert output["fraud_risk"] is not None
    assert output["routing_decision"] is not None
    assert output["routing_decision"]["routing_queue"] in ["fast-track", "standard"]
