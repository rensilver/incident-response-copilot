"""Validate automatic LangSmith delivery or credential-free, tracing-disabled operation.

Each invocation runs one real Groq investigation against the seeded Docker data
services. Use separate processes and new output directories for enabled/disabled runs.
"""

import argparse
import asyncio
import json
import os
import platform
import subprocess
import time
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlsplit
from uuid import uuid4

import psutil
import requests
from dotenv import dotenv_values
from langchain_core.tracers.langchain import get_client
from langgraph.graph.state import CompiledStateGraph
from langsmith.schemas import Run
from langsmith.utils import LangSmithNotFoundError, tracing_is_enabled
from pydantic_core import to_jsonable_python

from incident_copilot.composition import build_collaborators
from incident_copilot.config.settings import Settings
from incident_copilot.services.incident_service import IncidentService, InvestigationRequest
from incident_copilot.utils.logging import configure_logging


def write_json(path: Path, value: Any) -> None:
    """Write selected evidence, never dumping settings or request headers."""
    path.write_text(json.dumps(to_jsonable_python(value), indent=2) + "\n")


class IdentifiedGraph:
    """Give the ordinary graph a known ID without injecting a tracing callback."""

    def __init__(self, graph: CompiledStateGraph, enabled: bool) -> None:  # type: ignore[type-arg]
        """Store a compiled graph and a unique lookup ID."""
        self.graph = graph
        self.run_id = uuid4()
        self.enabled = enabled
        self.initial: Any = None
        self.final: Mapping[str, Any] | None = None

    async def ainvoke(self, state: Any, /) -> Mapping[str, Any]:
        """Preserve the service path, adding only trace identity and labels."""
        self.initial = to_jsonable_python(state)
        final: Mapping[str, Any] = await self.graph.ainvoke(
            state,
            config={
                "run_id": self.run_id,
                "run_name": (
                    "langsmith-validation-enabled"
                    if self.enabled
                    else "langsmith-validation-disabled"
                ),
                "tags": ["release-validation", "synthetic-demo"],
            },
        )
        self.final = final
        return final


def flatten(run: Run) -> list[Run]:
    """Flatten remotely retrieved spans, including nested children."""
    result = [run]
    for child in run.child_runs or []:
        result.extend(flatten(child))
    return result


def remote_evidence(graph: IdentifiedGraph, output: Path) -> dict[str, Any]:
    """Flush the automatic tracer and poll LangSmith for the actual completed tree."""
    client = get_client()
    client.flush(timeout=30)
    deadline = time.monotonic() + 60
    polls = 0
    while True:
        polls += 1
        try:
            root = client.read_run(graph.run_id, load_child_runs=True)
        except LangSmithNotFoundError:
            root = None
        spans = flatten(root) if root else []
        names = {r.name for r in spans}
        types = Counter(r.run_type for r in spans)
        ready = bool(
            root
            and all(r.end_time is not None for r in spans)
            and {"supervisor", "metrics_agent", "logs_agent", "correlation_agent"} <= names
            and types["llm"] > 0
            and types["tool"] > 0
        )
        if ready or time.monotonic() >= deadline:
            break
        time.sleep(2)
    # Retain only useful remote fields; SDK extras may include runtime environment data.
    write_json(
        output / "remote-spans.json",
        [
            {
                "id": r.id,
                "trace_id": r.trace_id,
                "parent_run_id": r.parent_run_id,
                "name": r.name,
                "run_type": r.run_type,
                "start_time": r.start_time,
                "end_time": r.end_time,
                "error": r.error,
                "inputs": r.inputs,
                "outputs": r.outputs,
                "tags": r.tags,
            }
            for r in spans
        ],
    )
    return {
        "complete_tree_received": ready,
        "polls": polls,
        "span_count": len(spans),
        "span_types": dict(types),
        "errored_spans": sum(r.error is not None for r in spans),
        "root_input_matches_local": bool(root and root.inputs == graph.initial),
        "root_report_matches_local": bool(
            root
            and root.outputs
            and graph.final
            and root.outputs.get("report") == to_jsonable_python(graph.final["report"])
        ),
        "trace_url": client.get_run_url(run=root) if root else None,
    }


async def validate(output: Path, enabled: bool) -> bool:
    """Retain one live attempt, including failures; never retry an investigation."""
    output.mkdir(parents=True, exist_ok=False)
    # Settings handles the app config. These optional SDK-only fields need exporting
    # for a host invocation; Docker already exports env_file to the process.
    local = dotenv_values(".env")
    for key in ("LANGSMITH_ENDPOINT", "LANGSMITH_WORKSPACE_ID"):
        if local.get(key) and key not in os.environ:
            os.environ[key] = str(local[key])
    settings = Settings(
        langsmith_tracing=enabled, **({} if enabled else {"langsmith_api_key": None})
    )
    configure_logging(settings.log_level)
    evidence: dict[str, Any] = {
        "started_at": datetime.now(UTC),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "mode": "enabled" if enabled else "disabled",
        "provider": settings.llm_provider.value,
        "model": settings.groq_model,
        "fallback": settings.llm_fallback_provider,
        "project": settings.langsmith_project,
        "langsmith_key_supplied_to_settings": bool(settings.langsmith_api_key),
        "python": platform.python_version(),
        "packages": {
            p: version(p) for p in ("langsmith", "langchain-core", "langgraph", "langchain-groq")
        },
        "ram_total_mib": psutil.virtual_memory().total / 1024**2,
        "ram_available_before_mib": psutil.virtual_memory().available / 1024**2,
        "execution": "host IncidentService with real Groq and Docker data services; no HTTP/UI",
    }
    network: list[dict[str, Any]] = []
    original_request = requests.Session.request

    def observe_request(
        session: requests.Session, method: str, url: str, **kwargs: Any
    ) -> requests.Response:
        parsed = urlsplit(url)
        event: dict[str, Any] = {"method": method, "host": parsed.hostname, "path": parsed.path}
        network.append(event)
        response = original_request(session, method, url, **kwargs)
        event["status_code"] = response.status_code
        return response

    collaborators = build_collaborators(settings)
    graph = IdentifiedGraph(collaborators.graph, enabled)
    evidence["root_run_id"] = str(graph.run_id)
    evidence["sdk_tracing_enabled"] = tracing_is_enabled()
    request = InvestigationRequest(
        query="checkout-service memory keeps climbing; investigate metrics and logs",
        service="checkout-service",
        minutes_back=180,
    )
    evidence["request"] = request.model_dump()
    passed = False
    try:
        with patch.object(requests.Session, "request", observe_request):
            started = time.perf_counter()
            try:
                report = await asyncio.wait_for(
                    IncidentService(graph).investigate(request), timeout=180
                )
                evidence["report"] = report.model_dump(mode="json")
                evidence["investigation_error"] = None
            except Exception as exc:
                evidence["investigation_error"] = {"type": type(exc).__name__, "message": str(exc)}
            finally:
                evidence["service_seconds"] = time.perf_counter() - started
                write_json(
                    output / "local-graph.json", {"initial": graph.initial, "final": graph.final}
                )
            if enabled:
                evidence["delivery"] = await asyncio.to_thread(remote_evidence, graph, output)
                delivery = evidence["delivery"]
                passed = all(
                    delivery[k]
                    for k in (
                        "complete_tree_received",
                        "root_input_matches_local",
                        "root_report_matches_local",
                    )
                )
            else:
                # Allow background SDK work a chance to surface. No client is manually
                # created in this branch, and no tracer/context override is injected.
                await asyncio.sleep(2)
                evidence["requests_transport_calls"] = network.copy()
                passed = not network and tracing_is_enabled() is False
            passed = passed and evidence["investigation_error"] is None
    except Exception as exc:
        evidence["validation_error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        await collaborators.metrics_source.aclose()
        await collaborators.log_source.aclose()
        evidence["requests_transport_calls"] = network
        evidence["finished_at"] = datetime.now(UTC)
        evidence["passed"] = passed
        write_json(output / "result.json", evidence)
    print(
        json.dumps(
            {
                "mode": evidence["mode"],
                "passed": passed,
                "root_run_id": str(graph.run_id),
                "service_seconds": evidence.get("service_seconds"),
            }
        )
    )
    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("enabled", "disabled"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if asyncio.run(validate(args.output, args.mode == "enabled")) else 1)
