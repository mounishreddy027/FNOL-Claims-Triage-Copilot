"""
Unit Tests for Tool Schemas, Pydantic Boundary Contracts & Parameter Validation
Business Case ID: BC-AAIE-HACK-06 (AC-01 / AC-04 / AC-05 / AC-10)
"""

import pytest
from pydantic import ValidationError
from mcp_server.server import lookup_policy_details, calculate_claim_risk_score, get_standard_guidelines
from src.tools.rag_tool import PolicyRAGTool, get_policy_rag_tool
from src.graph import (
    ClaimClassificationResult,
    CoverageCheckResult,
    FraudScreeningResult,
    RoutingDecisionResult
)


class TestMCPToolContracts:
    """Test suite for FastMCP tool input/output contracts and schemas."""

    def test_lookup_policy_details_schema(self):
        """Verify lookup_policy_details schema, return types, and masked fields."""
        res = lookup_policy_details(policy_number="POL-12345-CA")
        assert isinstance(res, dict)
        assert "policy_number_masked" in res
        assert res["policy_number_masked"] == "POL-***-CA"
        assert res["status"] == "ACTIVE"
        assert "coverages" in res
        assert "collision" in res["coverages"]
        assert "limit" in res["coverages"]["collision"]
        assert "deductible" in res["coverages"]["collision"]
        assert isinstance(res["covered_vehicles"], list)

    def test_calculate_claim_risk_score_schema(self):
        """Verify calculate_claim_risk_score input types and score bounds."""
        res = calculate_claim_risk_score(
            damage_amount=15000.0,
            incident_type="Auto Collision",
            claimant_tenure_months=6,
            prior_claims_count=1
        )
        assert isinstance(res, dict)
        assert "claim_risk_score" in res
        assert 0.0 <= res["claim_risk_score"] <= 1.0
        assert res["risk_tier"] in ["LOW", "MEDIUM", "HIGH"]
        assert isinstance(res["contributing_factors"], list)
        assert res["recommended_action"] in ["FAST_TRACK_ELIGIBLE", "ADJUSTER_REVIEW", "SIU_INVESTIGATION"]

    def test_calculate_claim_risk_score_extremes(self):
        """Verify risk score calculates high risk on extreme factors."""
        res = calculate_claim_risk_score(
            damage_amount=50000.0,
            incident_type="Auto Collision",
            claimant_tenure_months=1,
            prior_claims_count=3
        )
        assert res["claim_risk_score"] >= 0.65
        assert res["risk_tier"] == "HIGH"
        assert res["recommended_action"] == "SIU_INVESTIGATION"

    def test_mcp_resource_contract(self):
        """Verify policy guidelines resource returns valid Markdown string."""
        content = get_standard_guidelines()
        assert isinstance(content, str)
        assert "Standard Claims Triage Guidelines" in content
        assert "Fast-Track Qualification" in content
        assert "Mandatory Human Escalation" in content


class TestRAGToolContract:
    """Test suite for PolicyRAGTool schema and response structures."""

    def test_rag_tool_schema_conformance(self):
        """Verify search_policy_coverage returns conformant dictionary structure."""
        rag = get_policy_rag_tool()
        res = rag.search_policy_coverage("Collision with another vehicle on highway", top_k=3)
        
        assert isinstance(res, dict)
        assert "query" in res
        assert "is_covered" in res
        assert isinstance(res["is_covered"], bool)
        assert "primary_clause_id" in res
        assert "clause_citation" in res
        assert "deductible" in res
        assert isinstance(res["deductible"], float)
        assert "limit" in res
        assert isinstance(res["limit"], float)
        assert "retrieved_matches" in res
        assert len(res["retrieved_matches"]) <= 3


class TestPydanticNodeBoundaryContracts:
    """Test suite enforcing strict Pydantic validation at agent node boundaries."""

    def test_claim_classification_valid(self):
        """Verify valid ClaimClassificationResult instantiation."""
        model = ClaimClassificationResult(
            claim_type="Auto Collision",
            severity="Low",
            estimated_damage=2500.0,
            loss_summary="Minor bumper dent",
            confidence=0.95
        )
        assert model.severity == "Low"
        assert model.estimated_damage == 2500.0

    def test_claim_classification_invalid_severity(self):
        """Verify invalid severity tier raises ValidationError."""
        with pytest.raises(ValidationError):
            ClaimClassificationResult(
                claim_type="Auto Collision",
                severity="Critical",  # Not in ["Low", "Medium", "High", "Severe"]
                estimated_damage=2500.0,
                loss_summary="Minor bumper dent",
                confidence=0.95
            )

    def test_claim_classification_negative_damage(self):
        """Verify negative damage amount raises ValidationError."""
        with pytest.raises(ValidationError):
            ClaimClassificationResult(
                claim_type="Auto Collision",
                severity="Low",
                estimated_damage=-500.0,  # ge=0.0
                loss_summary="Negative damage",
                confidence=0.95
            )

    def test_coverage_check_result_contract(self):
        """Verify CoverageCheckResult rejects negative deductibles."""
        with pytest.raises(ValidationError):
            CoverageCheckResult(
                is_covered=True,
                coverage_type="Auto Collision",
                applied_clause_id="POL-SEC-04-COLLISION",
                clause_citation="Standard collision clause",
                deductible=-100.0,  # ge=0.0
                coverage_limit=50000.0,
                rationale="Invalid negative deductible"
            )

    def test_fraud_screening_result_score_bounds(self):
        """Verify FraudScreeningResult strictly bounds fraud_risk_score between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            FraudScreeningResult(
                fraud_risk_score=1.5,  # le=1.0
                risk_tier="HIGH",
                triggered_indicators=["Extreme anomaly"],
                requires_siu_referral=True,
                rationale="Out of bounds score"
            )

    def test_routing_decision_result_invalid_queue(self):
        """Verify RoutingDecisionResult rejects unknown queue names."""
        with pytest.raises(ValidationError):
            RoutingDecisionResult(
                routing_queue="instant_payout",  # Not in ["fast-track", "standard", "investigate", "escalate_human"]
                auto_approved=True,
                rationale="Invalid queue"
            )
