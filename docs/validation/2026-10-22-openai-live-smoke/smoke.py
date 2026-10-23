"""Run one bounded live adapter smoke attempt; retain only allowlisted evidence."""

# ruff: noqa: E402 -- tracing flags and checkout imports must be configured before SDK imports.

import asyncio
import json
import logging
import os
import platform
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal

# Set before importing either SDK. This check never delivers LangSmith traces.
for flag in ("LANGSMITH_TRACING", "LANGSMITH_TRACING_V2", "LANGCHAIN_TRACING_V2"):
    os.environ[flag] = "false"
logging.disable(logging.CRITICAL)
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend" / "src"))

import httpx
from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.openai_provider import OpenAIProvider
from incident_copilot.models.enums import LLMProviderName
from incident_copilot.utils.exceptions import LLMUpstreamError
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langsmith import tracing_context
from pydantic import BaseModel, ConfigDict


class SmokeObject(BaseModel):
    """Tiny schema whose content is wholly synthetic."""

    model_config = ConfigDict(extra="forbid")
    result: Literal["smoke-ok"]


def smoke_add(left: int, right: int) -> int:
    """Add two synthetic integers without external I/O."""
    return left + right


async def run(output: Path) -> bool:
    """Exercise text, local JSON validation, and one complete tool exchange."""
    output.mkdir(parents=True, exist_ok=False)
    evidence: dict[str, Any] = {
        "started_at": datetime.now(UTC).isoformat(),
        "live": True,
        "model": "gpt-6-luna",
        "reasoning": {"effort": "none"},
        "tracing": False,
        "timeout_seconds_per_operation": 30,
        "max_output_tokens": 256,
        "max_http_requests": 4,
        "transport_retries": 0,
        "structured_attempts": 1,
        "versions": {
            name: version(name) for name in ("openai", "langchain-openai", "langchain-core")
        },
        "python": platform.python_version(),
        "requests": [],
        "steps": [],
    }
    requests: list[dict[str, Any]] = evidence["requests"]
    steps: list[dict[str, Any]] = evidence["steps"]
    provider: OpenAIProvider | None = None

    async def request_hook(request: httpx.Request) -> None:
        if len(requests) >= 4 or str(request.url) != "https://api.openai.com/v1/responses":
            raise ValueError("Smoke request budget or destination rejected")
        body = json.loads(request.content)
        items = body.get("input", [])
        calls = {item["call_id"] for item in items if item.get("type") == "function_call"}
        results = {item["call_id"] for item in items if item.get("type") == "function_call_output"}
        policy_matches = (
            body.get("model") == "gpt-6-luna"
            and body.get("reasoning") == {"effort": "none"}
            and body.get("max_output_tokens") == 256
            and "previous_response_id" not in body
        )
        requests.append(
            {
                "policy_matches": policy_matches,
                "json_object_mode": body.get("text", {}).get("format", {}).get("type")
                == "json_object",
                "tool_schema_count": len(body.get("tools", [])),
                "tool_call_count": len(calls),
                "tool_result_count": len(results),
                "tool_ids_paired": bool(calls) and calls == results,
            }
        )
        if not policy_matches:
            raise ValueError("Smoke model policy rejected")

    async def response_hook(response: httpx.Response) -> None:
        record = requests[-1]
        record["http_status"] = response.status_code
        if response.is_success:
            body = json.loads(await response.aread())
            record["completed"] = body.get("status") == "completed"
            record["response_model_matches"] = body.get("model") == "gpt-6-luna"
            usage = body.get("usage") or {}
            record["usage"] = {
                key: value
                for key in ("input_tokens", "output_tokens", "total_tokens")
                if type(value := usage.get(key)) is int
            }

    async def attempt(name: str, operation: Callable[[], Awaitable[None]]) -> None:
        started = time.monotonic()
        before = len(requests)
        step: dict[str, Any] = {"name": name}
        try:
            await operation()
            step["passed"] = True
        except Exception as exc:  # Evidence boundary: never serialize vendor messages/tracebacks.
            step["passed"] = False
            step["error_type"] = type(exc).__name__
            if isinstance(exc, LLMUpstreamError):
                step["failure_kind"] = exc.kind.value
        step["elapsed_seconds"] = round(time.monotonic() - started, 3)
        step["http_requests"] = len(requests) - before
        steps.append(step)
        (output / "result.json").write_text(json.dumps(evidence, indent=2) + "\n")

    try:
        # Read the configured key/model through Settings; never dump the settings.
        # Legacy provider selection and tracing are irrelevant to this adapter check.
        settings = Settings(
            llm_provider=LLMProviderName.OPENAI,
            llm_fallback_provider="none",
            langsmith_tracing=False,
            llm_operation_timeout_seconds=30,
            llm_max_output_tokens=256,
            llm_max_structured_attempts=1,
        )
        provider = await OpenAIProvider.from_settings(settings)
        # Evidence-only inspection of the owned SDK transport, without replacing
        # clients, serializer, adapter methods, HTTP responses, or error handling.
        assert provider._owned_clients is not None
        client = provider._owned_clients[1]._client
        client.event_hooks["request"].append(request_hook)
        client.event_hooks["response"].append(response_hook)
        active = provider

        async def text() -> None:
            result = await active.complete(
                [ChatMessage(role="user", content="Reply with exactly smoke-ok and nothing else.")]
            )
            assert result.strip() == "smoke-ok", "Unexpected text content"

        async def structured() -> None:
            result = await active.complete_structured(
                [ChatMessage(role="user", content='Return JSON: {"result":"smoke-ok"}.')],
                SmokeObject,
                max_attempts=1,
            )
            assert result.result == "smoke-ok"

        async def tool_exchange() -> None:
            tool = StructuredTool.from_function(smoke_add)
            runnable = active.bind_tools([tool])
            prompt = HumanMessage(
                content=(
                    "Call smoke_add once with left=19 and right=23. "
                    "After receiving its result, reply with only that number."
                )
            )
            reply = await runnable.ainvoke([prompt])
            assert isinstance(reply, AIMessage) and len(reply.tool_calls) == 1
            call = reply.tool_calls[0]
            assert call["name"] == tool.name and call["args"] == {"left": 19, "right": 23}
            result = await tool.ainvoke(call["args"])
            assert result == 42
            final = await runnable.ainvoke(
                [prompt, reply, ToolMessage(content=str(result), tool_call_id=call["id"])]
            )
            assert isinstance(final, AIMessage) and not final.tool_calls
            assert final.text.strip() == "42"
            assert requests[-1]["tool_ids_paired"]

        with tracing_context(enabled=False):
            await attempt("text", text)
            await attempt("structured", structured)
            await attempt("tool_continuation", tool_exchange)
    except Exception as exc:  # Retain setup failures without settings or raw error payloads.
        evidence["setup_error_type"] = type(exc).__name__
    finally:
        if provider is not None:
            await attempt("cleanup", provider.aclose)
        evidence["finished_at"] = datetime.now(UTC).isoformat()
        evidence["passed"] = (
            "setup_error_type" not in evidence
            and len(steps) == 4
            and all(step["passed"] for step in steps)
            and len(requests) == 4
            and all(request.get("completed") for request in requests)
        )
        (output / "result.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    return bool(evidence["passed"])


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run(ROOT / sys.argv[1])) else 1)
