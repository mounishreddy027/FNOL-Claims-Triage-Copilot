"""
Automated Tool Log Reconciliation Test (AC-07 Verification)
Business Case ID: BC-AAIE-HACK-06

Verifies that every tool invocation recorded in logs/tool_calls.jsonl matches
a registered tool on the MCP server or within the @tool registry.
"""

import os
import json
import pytest

from mcp_server.server import (
    lookup_policy_details,
    calculate_claim_risk_score,
    get_standard_guidelines
)

# Known registered MCP tools and @tool functions
REGISTERED_TOOLS = {
    "lookup_policy_details",
    "calculate_claim_risk_score",
    "get_standard_guidelines",
    "rag_search_policy_coverage",
    "search_policy_coverage",
    "PolicyRAGTool.search_policy_coverage",
    "retrieve_policy_clauses",
    "recall_prior_claims",
    "semantic_memory_search"
}


def test_tool_log_reconciles_with_registry():
    """Assert all tool calls in logs/tool_calls.jsonl map to legitimate registered tools."""
    log_file = "logs/tool_calls.jsonl"
    if not os.path.exists(log_file):
        pytest.skip("logs/tool_calls.jsonl does not exist yet (will be created on first run)")

    with open(log_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) > 0, "logs/tool_calls.jsonl should not be empty"

    unrecognized_tools = []
    for line in lines:
        record = json.loads(line)
        tool_name = record.get("tool_name")
        # Strip potential mcp_ prefix if logged
        clean_name = tool_name.replace("mcp_tool_", "").replace("mcp_", "")
        if clean_name not in REGISTERED_TOOLS and tool_name not in REGISTERED_TOOLS:
            unrecognized_tools.append(tool_name)

        # Assert trace context exists and is formatted as valid hex
        trace_id = record.get("trace_id", "")
        span_id = record.get("span_id", "")
        assert len(trace_id) == 32, f"Expected 32-hex trace_id, got: {trace_id}"
        assert len(span_id) == 16, f"Expected 16-hex span_id, got: {span_id}"

        # Assert sensitive IDs are masked in logged args and result
        record_str = json.dumps(record)
        import re
        assert not re.search(r"\bPOL-\d{4,10}-[A-Z]{2}\b", record_str), f"Unmasked policy number leaked in tool log: {record_str}"
        assert not re.search(r"\bCLM-\d{4,10}-[A-Z]{2}\b", record_str), f"Unmasked claimant ID leaked in tool log: {record_str}"

    assert len(unrecognized_tools) == 0, f"Unrecognized tools in tool_calls.jsonl: {unrecognized_tools}"
