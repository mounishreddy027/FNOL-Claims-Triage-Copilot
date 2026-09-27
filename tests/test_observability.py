"""
Unit Tests for Arize Phoenix Observability, OTel Spans, and Consequential Audit Trail
Business Case ID: BC-AAIE-HACK-06 (AC-07, AC-08, AC-09, AC-10)
"""

import os
import json
import pytest
import pandas as pd
from src.observability.tracing import (
    setup_phoenix_tracing,
    record_span,
    export_spans,
    calculate_golden_signals,
    _COLLECTED_SPANS
)
from src.observability.audit import log_agent_action, AUDIT_LOG_FILE


class TestObservabilityAndTracing:
    """Test suite for Phoenix OpenInference tracing and metrics."""

    def test_setup_phoenix_tracing(self):
        """Verify Phoenix setup initializes cleanly without exceptions."""
        setup_phoenix_tracing(project_name="fnol-claims-test", launch_ui=False)
        assert os.environ.get("PHOENIX_PROJECT_NAME") == "fnol-claims-test"

    def test_record_and_export_spans(self):
        """Verify spans are recorded with tokens, latency, and exported to Parquet and JSONL."""
        span = record_span(
            name="test_worker_agent",
            span_type="AGENT",
            inputs={"claim_id": "CLM-TEST-99"},
            outputs={"decision": "covered"},
            latency_ms=18.5,
            status="OK"
        )
        assert span["name"] == "test_worker_agent"
        assert span["latency_ms"] == 18.5
        assert "attributes.token_count.total" in span
        assert len(_COLLECTED_SPANS) > 0

        # Test span export
        parquet_file = "traces/test_spans.parquet"
        jsonl_file = "traces/test_spans.jsonl"
        df = export_spans(parquet_path=parquet_file, jsonl_path=jsonl_file)
        
        assert os.path.exists(parquet_file)
        assert os.path.exists(jsonl_file)
        
        read_df = pd.read_parquet(parquet_file)
        assert len(read_df) >= 1
        assert "span_id" in read_df.columns
        assert "latency_ms" in read_df.columns
        assert "span_type" in read_df.columns

    def test_golden_signals_calculation(self):
        """Verify golden signals report generates valid metrics."""
        signals = calculate_golden_signals()
        
        assert "total_spans" in signals
        assert "total_tokens" in signals
        assert "estimated_cost_usd" in signals
        assert "latency_metrics" in signals
        assert "p50_latency_ms" in signals["latency_metrics"]
        assert "p95_latency_ms" in signals["latency_metrics"]
        assert signals["success_rate"] == 1.0
        assert os.path.exists("reports/golden_signals.json")


class TestConsequentialActionAudit:
    """Test suite for AC-10 consequential action logging."""

    def test_audit_log_record_structure(self):
        """Verify consequential actions are appended with {actor, action, tool, decision, timestamp}."""
        test_action = "COVERAGE_DETERMINATION"
        test_actor = "CoverageCheckAgent"
        test_decision = {"is_covered": True, "clause": "POL-SEC-04-COLLISION"}
        
        log_agent_action(
            actor=test_actor,
            action=test_action,
            tool="PolicyRAGTool",
            decision=test_decision,
            details={"masked_policy": "POL-***-US"}
        )
        
        assert os.path.exists(AUDIT_LOG_FILE)
        
        # Read last line of audit log
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        assert len(lines) > 0
        last_record = json.loads(lines[-1])
        assert last_record["actor"] == test_actor
        assert last_record["action"] == test_action
        assert last_record["tool"] == "PolicyRAGTool"
        assert last_record["decision"] == test_decision
        assert "timestamp" in last_record
