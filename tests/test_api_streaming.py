"""
Unit Tests for FastAPI Streaming API (Rubric Section 7.7 / 8.1 Bonus / Extra Credit)
Business Case ID: BC-AAIE-HACK-06
"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app


@pytest.fixture(scope="module")
def client():
    """Create TestClient fixture for FastAPI application."""
    return TestClient(app)


def test_api_health_check(client):
    """Verify /health returns 200 and toolchain details."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "toolchain" in data
    assert data["toolchain"]["orchestrator"] == "LangGraph (StateGraph)"


def test_api_sync_triage_claim(client):
    """Verify /triage successfully executes claim triage and returns structured response."""
    payload = {
        "claim_id": "CLM-API-TEST-001",
        "claimant_id": "CLM-1001-M",
        "policy_number": "POL-554432-CA",
        "narrative": "Minor parking barrier bumper contact at 5 mph. Scratched plastic bumper cover. No injuries.",
        "loss_location": "San Jose, CA"
    }
    response = client.post("/triage", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["claim_id"] == "CLM-API-TEST-001"
    assert data["routing_queue"] in ["fast-track", "standard", "investigate", "escalate_human"]
    assert "trace_id" in data
    assert len(data["trace_id"]) == 32


def test_api_streaming_triage_events(client):
    """Verify /triage/stream streams Server-Sent Events (SSE)."""
    payload = {
        "claim_id": "CLM-API-STREAM-001",
        "claimant_id": "CLM-1002-M",
        "policy_number": "POL-554432-CA",
        "narrative": "Rear bumper tap at stoplight. Light dent in bumper.",
        "loss_location": "San Francisco, CA"
    }
    response = client.post("/triage/stream", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    content = response.text
    assert "event: lifecycle" in content
    assert "event: complete" in content
