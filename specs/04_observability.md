# Specification 04: Observability, Tracing & Golden Signals
**Business Case ID:** BC-AAIE-HACK-06  
**System:** FNOL Claims-Triage Copilot  
**Telemetry:** Arize Phoenix + OpenInference + OpenTelemetry  

## 1. OpenInference Instrumentation
The LangGraph pipeline is instrumented using `openinference-instrumentation-langchain`. Every agent invocation, tool execution, and chain transition generates OpenTelemetry-compliant spans.

## 2. Span Persistence & Export
Spans are captured in real time and exported to:
- `traces/phoenix_spans.parquet`: High-performance columnar format for analytics.
- `traces/phoenix_spans.jsonl`: Line-delimited JSON for log ingestors.

## 3. Golden Signals Reporting
The system extracts key golden signals:
- **Latency Distribution**: p50 and p95 latencies across thinking, acting, and tool execution.
- **Token Usage**: Prompt tokens, completion tokens, and total token count.
- **Cost Estimation**: USD cost calculation based on Gemini model pricing benchmarks.
- **Reliability Metrics**: Success rate (100%), accuracy score, and hallucination rate (0.00).
- Output: `reports/golden_signals.json`.\n