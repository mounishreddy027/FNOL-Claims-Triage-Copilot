"""
One-Command Complete Project Execution Entrypoint
Business Case ID: BC-AAIE-HACK-06

Executes the full FNOL Claims-Triage Copilot pipeline:
1. Automated Test Suite (72 Pytest Unit Tests)
2. DeepEval LLM-as-Judge Benchmark (Faithfulness & Hallucination with Gemini)
3. Multi-Agent Claims Triage Batch Evaluation (4 Benchmark Scenarios)
4. Arize Phoenix OTel Traces & Golden Signals Telemetry

Usage:
    python run.py
"""

import sys
from dotenv import load_dotenv

load_dotenv()
from src.cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(["--mode", "all"])
    main()
