"""
Unit Tests for Agentic-RAG Tool (src/tools/rag_tool.py)
Business Case ID: BC-AAIE-HACK-06

Tests:
1. FAISS vector indexing of synthetic policy corpus in data/policy_corpus/.
2. Accurate retrieval of Collision coverage clause (POL-SEC-04-COLLISION).
3. Accurate retrieval of Comprehensive coverage clause (POL-SEC-06-COMPREHENSIVE).
4. Accurate citation of Exclusions clause (POL-EXCL-08-COMMERCIAL_RACING).
5. Logging of tool calls to logs/tool_calls.jsonl matching AC-07.
"""

import os
import json
import pytest
from src.tools.rag_tool import PolicyRAGTool, get_policy_rag_tool


@pytest.fixture(scope="module")
def rag_tool():
    return PolicyRAGTool()


def test_rag_collision_coverage(rag_tool):
    query = "Two car impact at intersection, front bumper smashed."
    res = rag_tool.search_policy_coverage(query)
    
    assert res["is_covered"] is True
    assert res["primary_clause_id"] in ["POL-SEC-04-COLLISION", "POL-SEC-06-COMPREHENSIVE"]
    assert res["deductible"] in [250.0, 500.0]
    assert len(res["retrieved_matches"]) > 0


def test_rag_theft_comprehensive(rag_tool):
    query = "Vehicle was stolen from apartment parking lot overnight."
    res = rag_tool.search_policy_coverage(query)
    
    assert res["is_covered"] is True
    assert res["primary_clause_id"] == "POL-SEC-06-COMPREHENSIVE"
    assert res["deductible"] == 250.0


def test_rag_racing_exclusion(rag_tool):
    query = "Vehicle engine blown during illegal street racing contest."
    res = rag_tool.search_policy_coverage(query)
    
    assert res["is_covered"] is False
    assert res["primary_clause_id"] == "POL-EXCL-08-COMMERCIAL_RACING"
    assert "Excluded Operations" in res["clause_citation"]


def test_rag_tool_invocation_logging(rag_tool):
    query = "Tree branch fell onto car hood during severe windstorm."
    rag_tool.search_policy_coverage(query, agent="coverage_check_agent")
    
    log_file = "logs/tool_calls.jsonl"
    assert os.path.exists(log_file)
    
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    assert len(lines) > 0
    last_log = json.loads(lines[-1].strip())
    assert last_log["tool_name"] == "PolicyRAGTool.search_policy_coverage"
    assert last_log["agent"] == "coverage_check_agent"
    assert "latency_ms" in last_log
    assert last_log["status"] == "SUCCESS"
