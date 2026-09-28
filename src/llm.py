"""
Google Gemini API Integration via LangChain with Rate Limiting and Deterministic Fallback
Business Case ID: BC-AAIE-HACK-06

Execution Policy:
- Exclusively uses Google Gemini API (gemini-2.0-flash / gemini-2.5-flash-lite).
- Employs ChatGoogleGenerativeAI with InMemoryRateLimiter to prevent 429 quota exhaustion.
- Directly traced by OpenInference & OpenTelemetry via LangChain auto-instrumentation,
  producing genuine LLM spans with non-estimated token counts.
- If Gemini API key is absent, empty, quota-exhausted (429), or network is offline,
  the system automatically logs the event and falls back to deterministic offline rules.
"""

import os
import json
import logging
import asyncio
from typing import Optional, Type, Any, Union
from dotenv import load_dotenv
from pydantic import BaseModel

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()
logger = logging.getLogger("fnol.llm")

# Rate limiter: default 0.25 requests/sec (1 per 4 seconds) to comfortably respect free-tier RPM limits
_rps = float(os.environ.get("GEMINI_RPS", "0.25"))
_limiter = InMemoryRateLimiter(
    requests_per_second=_rps,
    check_every_n_seconds=0.1,
    max_bucket_size=1
)

_SHARED_LLM: Optional[ChatGoogleGenerativeAI] = None


def is_gemini_configured() -> bool:
    """Check if a valid Gemini API key is configured in the environment."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        return False
    clean_key = key.strip()
    return clean_key not in ["", "your_gemini_api_key_here", "your_api_key_here"]


def get_llm(model_name: Optional[str] = None) -> ChatGoogleGenerativeAI:
    """Get or create the shared rate-limited ChatGoogleGenerativeAI instance."""
    global _SHARED_LLM
    target_model = (
        model_name
        or os.environ.get("GEMINI_MODEL_NAME")
        or os.environ.get("GEMINI_MODEL")
        or "gemini-2.5-flash-lite"
    )

    api_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()

    # Recreate if model changed, uninitialized, or API key changed
    saved_key = getattr(_SHARED_LLM, "_saved_api_key", None) if _SHARED_LLM else None
    if _SHARED_LLM is None or _SHARED_LLM.model != target_model or saved_key != api_key:
        _SHARED_LLM = ChatGoogleGenerativeAI(
            model=target_model,
            google_api_key=api_key or "DUMMY_KEY",
            temperature=0.0,
            timeout=10.0,
            max_retries=1,
            rate_limiter=_limiter,
        )
        _SHARED_LLM._saved_api_key = api_key
    return _SHARED_LLM


def invoke_gemini_with_fallback(
    prompt: str,
    response_schema: Optional[Type[BaseModel]] = None,
    model_name: Optional[str] = None,
    system_instruction: Optional[str] = None,
) -> Optional[Any]:
    """Synchronously invoke Gemini with structured output validation and deterministic fallback."""
    if not is_gemini_configured():
        return None

    try:
        llm = get_llm(model_name=model_name)
        messages = []
        if system_instruction:
            messages.append(SystemMessage(content=system_instruction))
        messages.append(HumanMessage(content=prompt))

        if response_schema:
            runnable = llm.with_structured_output(response_schema)
            res = runnable.invoke(messages)
            return res
        else:
            res = llm.invoke(messages)
            if hasattr(res, "content"):
                if isinstance(res.content, list) and len(res.content) > 0:
                    first = res.content[0]
                    return first.get("text", "") if isinstance(first, dict) else str(first)
                return str(res.content)
            return str(res)
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            print(f"[Gemini Engine] !!! Quota/Rate Limit (429): engaging deterministic fallback.")
        else:
            print(f"[Gemini Engine] !!! LLM invocation notice ({e}): engaging fallback.")
        return None


async def ainvoke_gemini_with_fallback(
    prompt: str,
    response_schema: Optional[Type[BaseModel]] = None,
    model_name: Optional[str] = None,
    system_instruction: Optional[str] = None,
) -> Optional[Any]:
    """Asynchronously invoke Gemini with structured output validation and deterministic fallback."""
    if not is_gemini_configured():
        return None

    try:
        llm = get_llm(model_name=model_name)
        messages = []
        if system_instruction:
            messages.append(SystemMessage(content=system_instruction))
        messages.append(HumanMessage(content=prompt))

        if response_schema:
            runnable = llm.with_structured_output(response_schema)
            res = await runnable.ainvoke(messages)
            return res
        else:
            res = await llm.ainvoke(messages)
            if hasattr(res, "content"):
                if isinstance(res.content, list) and len(res.content) > 0:
                    first = res.content[0]
                    return first.get("text", "") if isinstance(first, dict) else str(first)
                return str(res.content)
            return str(res)
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            print(f"[Gemini Engine] !!! Quota/Rate Limit (429): engaging deterministic fallback.")
        else:
            print(f"[Gemini Engine] !!! Async LLM invocation notice ({e}): engaging fallback.")
        return None
