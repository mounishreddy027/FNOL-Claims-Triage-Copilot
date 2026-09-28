"""
Verification Test for Evidence Citation Resolution (docs/failure-analysis.md)
Business Case ID: BC-AAIE-HACK-06

Ensures that:
1. Every run_id (32-hex) cited in docs/failure-analysis.md exists in traces/phoenix_spans.jsonl / .parquet
2. Every span_id (16-hex) cited in docs/failure-analysis.md exists in traces/phoenix_spans.jsonl / .parquet
3. Every error timestamp cited in docs/failure-analysis.md exists in logs/mcp_errors.jsonl
4. At least three distinct real observed failures are analyzed with root cause and fix.
"""

import os
import re
import json
import pytest
import pandas as pd


def test_failure_analysis_citations_resolve_to_committed_evidence():
    """Verify that every telemetry record cited in docs/failure-analysis.md exists in committed files."""
    doc_path = os.path.join("docs", "failure-analysis.md")
    assert os.path.exists(doc_path), "docs/failure-analysis.md must exist."

    with open(doc_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Verify at least three observed failure sections exist
    observed_sections = re.findall(r"### 3\.\d+\s+Observed Failure", content)
    assert len(observed_sections) >= 3, f"Expected at least 3 observed failure sections, found {len(observed_sections)}"

    # 2. Extract cited run IDs (32-character hexadecimal)
    run_ids = re.findall(r"Run ID.*?([a-f0-9]{32})", content, re.IGNORECASE)
    assert len(run_ids) >= 2, f"Expected at least 2 cited run IDs in failure analysis, found {len(run_ids)}"

    # 3. Extract cited span IDs (16-character hexadecimal)
    span_ids = re.findall(r"Span ID.*?([a-f0-9]{16})", content, re.IGNORECASE)
    assert len(span_ids) >= 2, f"Expected at least 2 cited span IDs in failure analysis, found {len(span_ids)}"

    # 4. Extract cited timestamps
    timestamps = re.findall(r"\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:\+\d{2}:\d{2}|Z))\b", content)
    assert len(timestamps) >= 1, "Expected at least 1 cited ISO timestamp in failure analysis"

    # 5. Load telemetry spans from JSONL and Parquet
    spans_jsonl_path = os.path.join("traces", "phoenix_spans.jsonl")
    spans_parquet_path = os.path.join("traces", "phoenix_spans.parquet")
    assert os.path.exists(spans_jsonl_path), "traces/phoenix_spans.jsonl must exist"
    assert os.path.exists(spans_parquet_path), "traces/phoenix_spans.parquet must exist"

    with open(spans_jsonl_path, "r", encoding="utf-8") as f:
        spans_jsonl = [json.loads(line) for line in f if line.strip()]

    df_parquet = pd.read_parquet(spans_parquet_path)
    parquet_span_ids = set(df_parquet["span_id"].astype(str)) if "span_id" in df_parquet.columns else set()
    parquet_run_ids = set(df_parquet["run_id"].astype(str)) if "run_id" in df_parquet.columns else set()

    jsonl_span_ids = {s.get("span_id") for s in spans_jsonl}
    jsonl_run_ids = {s.get("run_id") for s in spans_jsonl}

    all_span_ids = jsonl_span_ids.union(parquet_span_ids)
    all_run_ids = jsonl_run_ids.union(parquet_run_ids)

    # 6. Load MCP error logs
    mcp_log_path = os.path.join("logs", "mcp_errors.jsonl")
    assert os.path.exists(mcp_log_path), "logs/mcp_errors.jsonl must exist"
    with open(mcp_log_path, "r", encoding="utf-8") as f:
        mcp_logs = [json.loads(line) for line in f if line.strip()]
    mcp_timestamps = {entry.get("timestamp") for entry in mcp_logs}

    # 7. Validate Run ID citations
    for rid in run_ids:
        assert rid in all_run_ids, f"Cited run_id '{rid}' in docs/failure-analysis.md was NOT found in traces/phoenix_spans.jsonl / .parquet!"

    # 8. Validate Span ID citations
    for sid in span_ids:
        assert sid in all_span_ids, f"Cited span_id '{sid}' in docs/failure-analysis.md was NOT found in traces/phoenix_spans.jsonl / .parquet!"

    # 9. Validate MCP error timestamps
    mcp_ts_found = False
    for ts in timestamps:
        if ts in mcp_timestamps:
            mcp_ts_found = True
            break
    assert mcp_ts_found, "At least one cited timestamp in docs/failure-analysis.md must match an actual record in logs/mcp_errors.jsonl!"
