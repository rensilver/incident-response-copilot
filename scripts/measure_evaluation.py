"""Retain measurements from the existing nine-run evaluation harness.

Run against freshly seeded local data services. This calls the same IncidentService,
run_scenario, and scoring function as make eval; it does not exercise HTTP or the UI.
"""

import argparse
import asyncio
import json
import platform
import subprocess
import threading
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import psutil
from langchain_core.callbacks import BaseCallbackHandler
from langgraph.graph.state import CompiledStateGraph
from pydantic_core import to_jsonable_python

from incident_copilot.composition import build_collaborators
from incident_copilot.config.settings import get_settings
from incident_copilot.evaluation.eval_runner import REPEATS, RunResult, _print_results, run_scenario
from incident_copilot.evaluation.scenarios import SCENARIOS
from incident_copilot.models.report import IncidentReport
from incident_copilot.services.incident_service import IncidentService, InvestigationRequest
from incident_copilot.utils.logging import configure_logging


def timestamp() -> str:
    """Return an explicitly UTC timestamp."""
    return datetime.now(UTC).isoformat()


def command(*args: str) -> str:
    """Capture a bounded read-only command, including any failure."""
    result = subprocess.run(args, capture_output=True, text=True, timeout=30, check=True)
    return result.stdout.strip()


def write_json(path: Path, value: Any) -> None:
    """Persist reviewable JSON without credentials from settings."""
    path.write_text(json.dumps(value, indent=2) + "\n")


def sample_memory(output: Path, stop: threading.Event) -> None:
    """Sample host, harness RSS, and project containers about every ten seconds."""
    with (output / "memory.jsonl").open("w") as stream:
        while not stop.is_set():
            vm, swap = psutil.virtual_memory(), psutil.swap_memory()
            sample: dict[str, Any] = {
                "timestamp": timestamp(),
                "host_available_mib": vm.available / 1024**2,
                "swap_used_mib": swap.used / 1024**2,
                "harness_rss_mib": psutil.Process().memory_info().rss / 1024**2,
            }
            try:
                sample["containers"] = [
                    json.loads(line)
                    for line in command(
                        "docker",
                        "stats",
                        "--no-stream",
                        "--format",
                        "{{json .}}",
                        "ic-app",
                        "ic-prometheus",
                        "ic-elasticsearch",
                        "ic-grafana",
                        "ic-ollama",
                    ).splitlines()
                ]
            except (subprocess.SubprocessError, OSError) as exc:
                sample["sampling_error"] = str(exc)
            stream.write(json.dumps(sample) + "\n")
            stream.flush()
            stop.wait(10)


class ToolEvidenceRecorder(BaseCallbackHandler):
    """Retain tool arguments and full returned findings for synthetic demo review."""

    def __init__(self) -> None:
        """Start an empty event list; callbacks may run from parallel specialists."""
        self.events: list[dict[str, Any]] = []

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Record model-selected arguments; the graph retains the enforced window."""
        self.events.append(
            {
                "event": "start",
                "run_id": str(run_id),
                "tool": serialized.get("name"),
                "inputs": to_jsonable_python(inputs if inputs is not None else input_str),
            }
        )

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        """Retain the typed tool output, including all sampled logs and metrics."""
        self.events.append(
            {"event": "end", "run_id": str(run_id), "output": to_jsonable_python(output)}
        )

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        """Keep tool failures even when the specialist recovers."""
        self.events.append({"event": "error", "run_id": str(run_id), "error": str(error)})


class RecordingGraph:
    """Observe the real graph without altering its requests, tools, or report."""

    def __init__(self, graph: CompiledStateGraph) -> None:  # type: ignore[type-arg]
        """Wrap the same compiled graph used by the ordinary evaluation harness."""
        self.graph = graph
        self.evidence: dict[str, Any] = {}

    async def ainvoke(self, state: Any, /) -> Mapping[str, Any]:
        """Capture tool events and final findings for one sequential investigation."""
        recorder = ToolEvidenceRecorder()
        self.evidence = {"initial_state": to_jsonable_python(state), "tools": recorder.events}
        final = await self.graph.ainvoke(state, config={"callbacks": [recorder]})
        self.evidence["final_state"] = to_jsonable_python(final)
        return final


class RecordingService:
    """Measure the service call while preserving the harness's error handling."""

    def __init__(self, service: IncidentService, graph: RecordingGraph) -> None:
        """Wrap the real service without changing requests or reports."""
        self.service = service
        self.graph = graph
        self.record: dict[str, Any] = {}

    async def investigate(self, request: InvestigationRequest) -> IncidentReport:
        """Retain a report or exception plus elapsed time, excluding pacing."""
        self.record = {"started_at": timestamp(), "request": request.model_dump()}
        started = time.perf_counter()
        try:
            report = await self.service.investigate(request)
            self.record["report"] = report.model_dump(mode="json")
            self.record["error"] = None
            return report
        except Exception as exc:
            self.record["report"] = None
            self.record["error"] = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            self.record["elapsed_seconds"] = time.perf_counter() - started
            self.record["finished_at"] = timestamp()
            self.record["evidence"] = self.graph.evidence


async def measure(output: Path, delay: float) -> None:
    """Run the unmodified scenario harness and retain every attempt immediately."""
    settings = get_settings()
    configure_logging(settings.log_level)
    output.mkdir(parents=True, exist_ok=False)
    safe_fields = {
        "llm_provider",
        "llm_fallback_provider",
        "groq_model",
        "groq_timeout_seconds",
        "ollama_model",
        "ollama_timeout_seconds",
        "ollama_num_ctx",
        "ollama_min_available_memory_mb",
        "max_tool_rounds",
        "max_supervisor_iterations",
        "langsmith_tracing",
        "log_level",
    }
    metadata = {
        "started_at": timestamp(),
        "source_commit": command("git", "rev-parse", "HEAD"),
        "source_status": command("git", "status", "--short"),
        "settings": settings.model_dump(mode="json", include=safe_fields),
        "execution": "host IncidentService via evaluation.run_scenario; Docker data services",
        "repeats_per_scenario": REPEATS,
        "delay_between_attempts_seconds": delay,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu": command("lscpu"),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cpus": psutil.cpu_count(),
        "ram_total_mib": psutil.virtual_memory().total / 1024**2,
        "swap_total_mib": psutil.swap_memory().total / 1024**2,
        "packages": {
            name: version(name)
            for name in (
                "incident-response-copilot",
                "langgraph",
                "langchain-core",
                "langchain-groq",
                "langchain-ollama",
                "groq",
                "pydantic",
                "httpx",
                "elasticsearch",
                "psutil",
            )
        },
        "docker_version": command("docker", "version", "--format", "{{json .}}"),
        "images": json.loads(command("docker", "compose", "images", "--format", "json")),
    }
    with httpx.Client(timeout=15) as client:
        for label, url in (
            ("health_before", "http://localhost:8000/health"),
            ("ollama_loaded_before", f"{settings.ollama_base_url}/api/ps"),
        ):
            response = client.get(url)
            response.raise_for_status()
            metadata[label] = response.json()
    write_json(output / "runtime.json", metadata)
    stop = threading.Event()
    sampler = threading.Thread(target=sample_memory, args=(output, stop), daemon=True)
    collaborators = build_collaborators(settings)
    graph = RecordingGraph(collaborators.graph)
    service = RecordingService(IncidentService(graph), graph)
    results: list[RunResult] = []
    records = []
    started = time.perf_counter()
    sampler.start()
    try:
        for scenario in SCENARIOS:
            for repeat in range(1, REPEATS + 1):
                if results:
                    await asyncio.sleep(delay)
                try:
                    result = await run_scenario(service, scenario)
                finally:
                    # Unexpected exceptions abort, but the attempt remains reviewable.
                    write_json(output / f"{scenario.name.value}-{repeat}.json", service.record)
                results.append(result)
                record = {
                    **service.record,
                    "scenario": scenario.name.value,
                    "repeat": repeat,
                    "expected_culprit": scenario.expected_culprit,
                    "correct": result.correct,
                    "detail": result.detail,
                }
                records.append(record)
                write_json(output / f"{scenario.name.value}-{repeat}.json", record)
                print(
                    f"MEASUREMENT {scenario.name.value} {repeat}/{REPEATS}: "
                    f"mention_match={result.correct} elapsed={record['elapsed_seconds']:.3f}s",
                    flush=True,
                )
        _print_results(results)
    finally:
        write_json(
            output / "summary.json",
            {
                "finished_at": timestamp(),
                "wall_seconds_including_pacing": time.perf_counter() - started,
                "planned_attempts": len(SCENARIOS) * REPEATS,
                "completed_attempts": len(records),
                "mention_matches": sum(r.correct for r in results),
                "investigation_errors": sum(r["error"] is not None for r in records),
                "runs": records,
            },
        )
        await collaborators.metrics_source.aclose()
        await collaborators.log_source.aclose()
        stop.set()
        await asyncio.to_thread(sampler.join, 35)
    with httpx.Client(timeout=15) as client:
        write_json(
            output / "after.json",
            {
                "timestamp": timestamp(),
                "health": client.get("http://localhost:8000/health").json(),
                "ollama_loaded": client.get(f"{settings.ollama_base_url}/api/ps").json(),
            },
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New artifact directory")
    parser.add_argument("--delay-seconds", type=float, default=65)
    args = parser.parse_args()
    if args.delay_seconds < 0:
        parser.error("--delay-seconds must be nonnegative")
    asyncio.run(measure(args.output, args.delay_seconds))
