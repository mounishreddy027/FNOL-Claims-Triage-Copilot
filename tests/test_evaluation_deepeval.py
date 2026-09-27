"""
Unit Tests for DeepEval Gemini LLM-as-Judge Evaluation Suite
Business Case ID: BC-AAIE-HACK-06 (AC-05 / AC-08)
"""

import os
import pytest
from scripts.eval_deepeval import GeminiJudgeLLM, get_benchmark_test_cases, run_deepeval_benchmark


def test_gemini_judge_initialization():
    """Verify GeminiJudgeLLM initializes with gemini model designation."""
    judge = GeminiJudgeLLM(model_name="gemini-2.0-flash")
    assert "gemini" in judge.get_model_name().lower()
    assert judge.load_model() == judge


def test_benchmark_test_cases_structure():
    """Verify all benchmark test cases contain input, actual_output, and context."""
    cases = get_benchmark_test_cases()
    assert len(cases) >= 4
    for c in cases:
        assert "input" in c
        assert "actual_output" in c
        assert "context" in c
        assert isinstance(c["context"], list)
        assert len(c["context"]) > 0


def test_deepeval_benchmark_execution():
    """Verify full benchmark executes cleanly and writes reports/deepeval_benchmark.json."""
    summary = run_deepeval_benchmark()
    assert "metrics_summary" in summary
    assert "average_faithfulness_score" in summary["metrics_summary"]
    assert "average_hallucination_score" in summary["metrics_summary"]
    assert os.path.exists("reports/deepeval_benchmark.json")
