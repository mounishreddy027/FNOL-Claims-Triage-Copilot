"""
Google Gemini API Integration with Automatic Deterministic Fallback
Business Case ID: BC-AAIE-HACK-06

Execution Policy:
- Exclusively uses Google Gemini API (gemini-2.0-flash / gemini-1.5-flash).
- When GEMINI_API_KEY or GOOGLE_API_KEY is provided and operational, all agent reasoning
  and LLM-as-judge benchmarks execute against live Google Gemini endpoints.
- If the Gemini API key is absent, empty, quota-exhausted, or network is offline,
  the system automatically and gracefully falls back to deterministic offline rules.
"""

import os
import json
import logging
from typing import Optional, Type, Any
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv()
logger = logging.getLogger("fnol.llm")


def is_gemini_configured() -> bool:
    """Check if a non-placeholder Gemini API key is set in environment."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        return False
    clean_key = key.strip()
    return clean_key not in ["", "your_gemini_api_key_here", "your_api_key_here"]


def get_gemini_client():
    """Retrieve an authenticated google-genai Client if configured, else None."""
    if not is_gemini_configured():
        return None
    api_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")).strip()
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as e:
        logger.warning(f"[Gemini Engine] Notice: genai.Client initialization failed: {e}")
        return None


import time

def _record_llm_span(
    model: str,
    prompt: str,
    response: str,
    latency_ms: float,
    status: str = "OK",
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None
):
    try:
        from src.observability.tracing import record_span
        record_span(
            name=f"gemini_call_{model}",
            span_type="LLM",
            inputs={"model": model, "prompt": prompt},
            outputs={"response": response},
            latency_ms=latency_ms,
            status=status,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens
        )
    except Exception:
        pass


def invoke_gemini_with_fallback(
    prompt: str,
    response_schema: Optional[Type[BaseModel]] = None,
    model_name: Optional[str] = None,
    system_instruction: Optional[str] = None
) -> Optional[Any]:
    """Invoke Google Gemini API with Pydantic structured output.
    
    Returns the validated Pydantic model (or string text).
    If Gemini is not configured, or if the API call fails/times out, returns None,
    signaling the caller to use deterministic offline fallback.
    """
    client = get_gemini_client()
    if not client:
        return None

    target_model = model_name or os.environ.get("GEMINI_MODEL_NAME") or os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash-lite"

    clean_preview = prompt.strip().replace("\n", " ")
    if len(clean_preview) > 90:
        clean_preview = clean_preview[:87] + "..."
    schema_label = response_schema.__name__ if response_schema else "free-text"

    print(f"[Gemini Engine] >>> CALLING MODEL: '{target_model}' | Schema: {schema_label}")
    print(f"[Gemini Engine]     Prompt Preview: \"{clean_preview}\"")

    t0 = time.time()
    try:
        from google.genai import types
        config = types.GenerateContentConfig(
            temperature=0.1,
            system_instruction=system_instruction
        )
        if response_schema:
            config.response_mime_type = "application/json"
            config.response_schema = response_schema

        response = client.models.generate_content(
            model=target_model,
            contents=prompt,
            config=config
        )

        latency_ms = max(1.0, (time.time() - t0) * 1000.0)

        # Extract actual model token counts from Gemini response metadata
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", None) if usage else None
        completion_tokens = getattr(usage, "candidates_token_count", None) if usage else None
        total_tokens = getattr(usage, "total_token_count", None) if usage else None

        if response and response.text:
            _record_llm_span(
                model=target_model,
                prompt=clean_preview,
                response=response.text[:200],
                latency_ms=latency_ms,
                status="OK",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
            if response_schema:
                data = json.loads(response.text)
                validated = response_schema.model_validate(data)
                print(f"[Gemini Engine] <<< SUCCESS: Live structured output validated against {schema_label}.")
                return validated
            print(f"[Gemini Engine] <<< SUCCESS: Live response text received ({len(response.text)} chars).")
            return response.text
        else:
            _record_llm_span(
                model=target_model,
                prompt=clean_preview,
                response="Empty response received",
                latency_ms=latency_ms,
                status="EMPTY",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
            print(f"[Gemini Engine] !!! Notice: Empty response from model '{target_model}'. Engaging fallback.")
            return None
    except Exception as e:
        latency_ms = max(1.0, (time.time() - t0) * 1000.0)
        err_msg = str(e)
        _record_llm_span(
            model=target_model,
            prompt=clean_preview,
            response=f"Fallback engaged: {err_msg[:120]}",
            latency_ms=latency_ms,
            status="FALLBACK"
        )
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            print(f"[Gemini Engine] !!! Quota/Rate Limit (429 RESOURCE_EXHAUSTED): Free tier limit reached. Engaging deterministic fallback.")
        else:
            print(f"[Gemini Engine] !!! Live API Call Error ({e}). Engaging deterministic fallback.")
        return None

    return None
