"""
Unit & Contract Tests for Custom MCP Server (mcp_server/)
Business Case ID: BC-AAIE-HACK-06

Tests:
1. lookup_policy_details tool returns valid structured policy data and masks IDs.
2. calculate_claim_risk_score tool evaluates actuarial factors and outputs risk tier.
3. policy://rules/standard_guidelines resource returns triage guidelines.
4. Committed transcript is written to logs/mcp_transcript.jsonl.
"""

import os
import json
import pytest
from mcp_server.server import lookup_policy_details, calculate_claim_risk_score, get_standard_guidelines
from mcp_server.client import LocalMCPClientAdapter


def test_mcp_tool_lookup_policy_details():
    raw_pol = "POL-883921-CA"
    result = lookup_policy_details(raw_pol)
    
    assert result["status"] == "ACTIVE"
    assert "POL-***-CA" in result["policy_number_masked"]
    assert "883921" not in result["policy_number_masked"]
    assert "collision" in result["coverages"]
    assert result["coverages"]["collision"]["limit"] == 50000.0
    assert result["coverages"]["collision"]["deductible"] == 500.0


def test_mcp_tool_calculate_claim_risk_score():
    # Low risk
    low_risk = calculate_claim_risk_score(
        damage_amount=2500.0,
        incident_type="Auto Collision",
        claimant_tenure_months=36,
        prior_claims_count=0
    )
    assert low_risk["risk_tier"] == "LOW"
    assert low_risk["claim_risk_score"] < 0.30
    assert low_risk["recommended_action"] == "FAST_TRACK_ELIGIBLE"

    # High risk
    high_risk = calculate_claim_risk_score(
        damage_amount=32000.0,
        incident_type="Auto Collision",
        claimant_tenure_months=1,
        prior_claims_count=3
    )
    assert high_risk["risk_tier"] == "HIGH"
    assert high_risk["claim_risk_score"] >= 0.65
    assert high_risk["recommended_action"] == "SIU_INVESTIGATION"
    assert len(high_risk["contributing_factors"]) >= 2


def test_mcp_resource_read():
    guidelines = get_standard_guidelines()
    assert "# Standard Claims Triage Guidelines" in guidelines
    assert "Fast-Track Qualification" in guidelines
    assert "Damage estimate <= $5,000.00" in guidelines


def test_mcp_transcript_logging():
    # Trigger an MCP call through client adapter
    LocalMCPClientAdapter.get_policy_details("POL-TRANSCRIPT-TEST")
    
    transcript_file = "logs/mcp_transcript.jsonl"
    assert os.path.exists(transcript_file)
    
    with open(transcript_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    assert len(lines) > 0
    last_record = json.loads(lines[-1].strip())
    assert "timestamp" in last_record
    assert "tool_name" in last_record
    assert "args" in last_record
    assert "status" in last_record
    assert last_record["status"] == "SUCCESS"
