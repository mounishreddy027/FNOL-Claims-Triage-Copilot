"""
MCP Client adapter consuming custom MCP server tools via langchain-mcp-adapters over stdio.
Business Case ID: BC-AAIE-HACK-06
"""

import sys
import os
import json
import time
import datetime
import asyncio
from typing import List, Dict, Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools

# Fallback direct server methods for resilience
from mcp_server.server import (
    lookup_policy_details as direct_lookup_policy_details,
    calculate_claim_risk_score as direct_calculate_claim_risk_score,
    get_standard_guidelines as direct_get_standard_guidelines
)
from src.memory.tiered_memory import mask_identifier

MCP_ERROR_LOG = "logs/mcp_errors.jsonl"


def _log_mcp_error(tool_name: str, args: Dict[str, Any], error: str):
    """Log tool failure with masked identifiers for audit and debugging."""
    os.makedirs("logs", exist_ok=True)
    masked_args = {}
    for k, v in args.items():
        if any(id_key in k.lower() for id_key in ["policy", "claimant", "vin", "id"]):
            masked_args[k] = mask_identifier(str(v))
        else:
            masked_args[k] = v

    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tool_name": tool_name,
        "args": masked_args,
        "error": str(error),
        "status": "ERROR"
    }
    with open(MCP_ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _record_mcp_span(tool_name: str, args: Dict[str, Any], result: Dict[str, Any], latency_ms: float, status: str = "OK"):
    try:
        from src.observability.tracing import record_span
        record_span(
            name=f"mcp_tool_{tool_name}",
            span_type="TOOL",
            inputs={"tool_name": tool_name, "args": args},
            outputs=result,
            latency_ms=latency_ms,
            status=status
        )
    except Exception:
        pass


class StdioMCPClientAdapter:
    """Manages MCP tool execution over stdio connection via langchain-mcp-adapters."""

    @staticmethod
    def get_server_params() -> StdioServerParameters:
        """Create StdioServerParameters pointing to the local MCP server."""
        server_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")
        env = dict(os.environ)
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        current_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{root_dir}{os.pathsep}{current_pythonpath}" if current_pythonpath else root_dir
        return StdioServerParameters(command=sys.executable, args=[server_script], env=env)

    @classmethod
    async def ainvoke_tool(cls, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Asynchronously execute a tool on the MCP server via stdio and langchain-mcp-adapters."""
        params = cls.get_server_params()
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await load_mcp_tools(session)
                    tool_map = {t.name: t for t in tools}

                    if tool_name not in tool_map:
                        raise ValueError(f"Tool '{tool_name}' not exposed by MCP server. Available: {list(tool_map.keys())}")

                    raw_res = await tool_map[tool_name].ainvoke(args)

                    if isinstance(raw_res, list) and len(raw_res) > 0:
                        first = raw_res[0]
                        if isinstance(first, dict) and "text" in first:
                            try:
                                return json.loads(first["text"])
                            except json.JSONDecodeError:
                                return {"result": first["text"]}
                    elif isinstance(raw_res, str):
                        try:
                            return json.loads(raw_res)
                        except json.JSONDecodeError:
                            return {"result": raw_res}
                    elif isinstance(raw_res, dict):
                        return raw_res

                    return {"result": raw_res}
        except Exception as exc:
            _log_mcp_error(tool_name, args, str(exc))
            return cls._fallback_direct_invoke(tool_name, args, str(exc))

    @classmethod
    def invoke_tool(cls, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronously execute a tool via stdio langchain-mcp-adapters with error handling."""
        t0 = time.time()
        res = None
        status = "OK"
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(lambda: asyncio.run(asyncio.wait_for(cls.ainvoke_tool(tool_name, args), timeout=6.0)))
                    res = future.result(timeout=8.0)
            else:
                async def _timed_call():
                    return await asyncio.wait_for(cls.ainvoke_tool(tool_name, args), timeout=6.0)
                res = asyncio.run(_timed_call())

            if isinstance(res, dict) and res.get("status") == "ERROR":
                status = "ERROR"
            return res
        except Exception as exc:
            status = "ERROR"
            _log_mcp_error(tool_name, args, str(exc))
            res = cls._fallback_direct_invoke(tool_name, args, str(exc))
            return res
        finally:
            latency_ms = max(0.5, (time.time() - t0) * 1000.0)
            _record_mcp_span(tool_name, args, res or {}, latency_ms, status=status)

    @classmethod
    async def aread_resource(cls, uri: str = "policy://rules/standard_guidelines") -> str:
        """Asynchronously read a resource over stdio from the MCP server."""
        from pydantic import AnyUrl
        params = cls.get_server_params()
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    res = await session.read_resource(AnyUrl(uri))
                    if res.contents and len(res.contents) > 0:
                        return res.contents[0].text
                    return ""
        except Exception as exc:
            _log_mcp_error(f"resource_{uri}", {"uri": uri}, str(exc))
            return direct_get_standard_guidelines()

    @classmethod
    def read_resource(cls, uri: str = "policy://rules/standard_guidelines") -> str:
        """Synchronously read an MCP resource over stdio with timeout and error fallback."""
        t0 = time.time()
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(lambda: asyncio.run(asyncio.wait_for(cls.aread_resource(uri), timeout=6.0)))
                    return future.result(timeout=8.0)
            else:
                return asyncio.run(asyncio.wait_for(cls.aread_resource(uri), timeout=6.0))
        except Exception as exc:
            _log_mcp_error(f"resource_{uri}", {"uri": uri}, str(exc))
            return direct_get_standard_guidelines()
        finally:
            latency_ms = max(0.5, (time.time() - t0) * 1000.0)
            _record_mcp_span("read_guidelines_resource", {"uri": uri}, {"retrieved": True}, latency_ms, status="OK")

    @staticmethod
    def _fallback_direct_invoke(tool_name: str, args: Dict[str, Any], error_reason: str) -> Dict[str, Any]:
        """Fallback to in-process execution with error logging when stdio transport fails."""
        try:
            if tool_name == "lookup_policy_details":
                res = direct_lookup_policy_details(args.get("policy_number", ""))
                res["_adapter_notice"] = f"stdio transport handled via direct fallback: {error_reason}"
                return res
            elif tool_name == "calculate_claim_risk_score":
                res = direct_calculate_claim_risk_score(
                    damage_amount=float(args.get("damage_amount", 0.0)),
                    incident_type=str(args.get("incident_type", "Collision")),
                    claimant_tenure_months=int(args.get("claimant_tenure_months", 24)),
                    prior_claims_count=int(args.get("prior_claims_count", 0))
                )
                res["_adapter_notice"] = f"stdio transport handled via direct fallback: {error_reason}"
                return res
            else:
                return {
                    "status": "ERROR",
                    "error": f"Tool '{tool_name}' failed: {error_reason}",
                    "tool": tool_name
                }
        except Exception as inner_e:
            return {
                "status": "ERROR",
                "error": f"Tool execution failed: {inner_e}",
                "original_error": error_reason,
                "tool": tool_name
            }


class LocalMCPClientAdapter:
    """Standardized MCP Client adapter consuming tools and resources via langchain-mcp-adapters over stdio."""

    @staticmethod
    def get_policy_details(policy_number: str) -> Dict[str, Any]:
        """Invoke lookup_policy_details over stdio via langchain-mcp-adapters."""
        return StdioMCPClientAdapter.invoke_tool("lookup_policy_details", {"policy_number": policy_number})

    @staticmethod
    def calculate_risk(
        damage_amount: float,
        incident_type: str,
        tenure_months: int = 24,
        prior_claims: int = 0
    ) -> Dict[str, Any]:
        """Invoke calculate_claim_risk_score over stdio via langchain-mcp-adapters."""
        return StdioMCPClientAdapter.invoke_tool(
            "calculate_claim_risk_score",
            {
                "damage_amount": damage_amount,
                "incident_type": incident_type,
                "claimant_tenure_months": tenure_months,
                "prior_claims_count": prior_claims
            }
        )

    @staticmethod
    def read_guidelines(uri: str = "policy://rules/standard_guidelines") -> str:
        """Read standard triage guidelines resource over the stdio MCP adapter."""
        return StdioMCPClientAdapter.read_resource(uri)

