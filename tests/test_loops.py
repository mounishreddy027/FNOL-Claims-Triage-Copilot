"""
Unit Tests for Recursion Limits and Loop Safeguards in LangGraph
Business Case ID: BC-AAIE-HACK-06 (AC-01 / NFR-02)
"""

import pytest
from langgraph.errors import GraphRecursionError
from src.graph import get_compiled_app, FNOLState, route_next_worker


@pytest.fixture
def compiled_app():
    app, checkpointer = get_compiled_app(db_path=":memory:")
    return app


def test_recursion_limit_enforcement(compiled_app):
    """Verify LangGraph raises GraphRecursionError when recursion_limit is set below required steps."""
    state: FNOLState = {
        "claim_id": "CLM-RECURSE-001",
        "claimant_id_masked": "CLM-***-US",
        "policy_number_masked": "POL-***-US",
        "raw_claim_text": "Minor collision with guardrail.",
        "quarantined_text": None,
        "is_quarantined": False,
        "incident_date": "2026-09-26",
        "loss_location": "Austin, TX",
        "classification": None,
        "coverage_result": None,
        "fraud_risk": None,
        "routing_decision": None,
        "current_step": "init",
        "next_agent": None,
        "audit_trail": [],
        "errors": []
    }

    # Set recursion_limit to 3 (standard flow requires ~8 transitions between supervisor and workers)
    config = {"configurable": {"thread_id": "thread-recurse-001"}, "recursion_limit": 3}
    
    with pytest.raises(GraphRecursionError):
        compiled_app.invoke(state, config=config)


def test_normal_execution_terminates_within_step_budget(compiled_app):
    """Verify normal claim execution completes well within standard recursion limits."""
    state: FNOLState = {
        "claim_id": "CLM-BUDGET-002",
        "claimant_id_masked": "CLM-***-US",
        "policy_number_masked": "POL-***-US",
        "raw_claim_text": "Rear-end collision at traffic stop. Rear bumper damaged.",
        "quarantined_text": None,
        "is_quarantined": False,
        "incident_date": "2026-09-26",
        "loss_location": "Dallas, TX",
        "classification": None,
        "coverage_result": None,
        "fraud_risk": None,
        "routing_decision": None,
        "current_step": "init",
        "next_agent": None,
        "audit_trail": [],
        "errors": []
    }

    # Standard budget is 25
    config = {"configurable": {"thread_id": "thread-budget-002"}, "recursion_limit": 25}
    result = compiled_app.invoke(state, config=config)
    
    assert result["current_step"] == "supervisor"
    assert result["next_agent"] == "end"
    assert result["routing_decision"] is not None
    # Transition count should be finite and bounded
    assert len(result["audit_trail"]) <= 12


def test_supervisor_loop_prevention_logic():
    """Verify route_next_worker conditional router guarantees monotonic progression without cycles."""
    # State 1: init -> claim_classification
    state1: FNOLState = {
        "classification": None,
        "coverage_result": None,
        "fraud_risk": None,
        "routing_decision": None,
        "next_agent": "claim_classification"
    }
    assert route_next_worker(state1) == "claim_classification"

    # State 2: classification done -> coverage_check
    state2: FNOLState = {
        "classification": {"claim_type": "Auto Collision"},
        "coverage_result": None,
        "fraud_risk": None,
        "routing_decision": None,
        "next_agent": "coverage_check"
    }
    assert route_next_worker(state2) == "coverage_check"

    # State 3: coverage done -> fraud_indicator
    state3: FNOLState = {
        "classification": {"claim_type": "Auto Collision"},
        "coverage_result": {"is_covered": True},
        "fraud_risk": None,
        "routing_decision": None,
        "next_agent": "fraud_indicator"
    }
    assert route_next_worker(state3) == "fraud_indicator"

    # State 4: fraud done -> routing_decision
    state4: FNOLState = {
        "classification": {"claim_type": "Auto Collision"},
        "coverage_result": {"is_covered": True},
        "fraud_risk": {"fraud_risk_score": 0.1},
        "routing_decision": None,
        "next_agent": "routing_decision"
    }
    assert route_next_worker(state4) == "routing_decision"

    # State 5: all done -> END
    state5: FNOLState = {
        "classification": {"claim_type": "Auto Collision"},
        "coverage_result": {"is_covered": True},
        "fraud_risk": {"fraud_risk_score": 0.1},
        "routing_decision": {"routing_queue": "fast-track"},
        "next_agent": "end"
    }
    assert route_next_worker(state5) == "__end__"
